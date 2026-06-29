#!/usr/bin/env node
/*
 * browser_fetch.cjs - headless-Chromium fetch tier for scrape.py
 * ---------------------------------------------------------------
 * The strongest tier of the fallback ladder: a real headless browser that
 * executes JavaScript and presents a genuine browser TLS/HTTP fingerprint,
 * which is what gets past most site-level 403 "bot detection" walls and
 * renders JS-only pages that a plain HTTP client receives empty.
 *
 * It reads ONE JSON request object from stdin and prints ONE JSON result
 * object to stdout. All human-readable logging goes to stderr so stdout stays
 * machine-parseable.
 *
 * Request  (stdin):  { url, timeoutMs, waitUntil, userAgent, extraHeaders,
 *                      proxy, tls12, screenshotPath, blockResources }
 * Result   (stdout): { ok, status, finalUrl, title, html, headers,
 *                      screenshotPath, error, errorType }
 *
 * KEY ENVIRONMENT FIX (verified empirically in this sandbox):
 *   The egress proxy re-terminates TLS (MITM). Chromium's default TLS 1.3
 *   ClientHello carries a post-quantum X25519MLKEM768 key_share (~1.2 KB),
 *   which bloats the ClientHello past a single record and makes the proxy
 *   close the connection (net::ERR_CONNECTION_CLOSED). Capping the
 *   browser<->proxy hop at TLS 1.2 (--ssl-version-max=tls1.2) shrinks the
 *   ClientHello so the proxy accepts it. This does NOT weaken security to the
 *   origin: the proxy, not the browser, makes the real TLS connection to the
 *   origin server. We enable the cap automatically whenever a proxy is in use.
 */
'use strict';

function loadPlaywright() {
  // Playwright may be installed locally, globally, or only reachable via the
  // Node global modules dir. Try each so the script is portable.
  const candidates = [
    'playwright',
    'playwright-core',
    '/opt/node22/lib/node_modules/playwright',
    '/usr/local/lib/node_modules/playwright',
    '/usr/lib/node_modules/playwright',
  ];
  for (const c of candidates) {
    try { return require(c); } catch (_) { /* keep trying */ }
  }
  // Last resort: honor NODE_PATH-style global dir if `npm root -g` is known.
  throw new Error(
    'Playwright is not installed. Install it with `npm i playwright` ' +
    'or point NODE_PATH at a global install that has it.'
  );
}

function readStdin() {
  return new Promise((resolve) => {
    let buf = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', (d) => { buf += d; });
    process.stdin.on('end', () => resolve(buf));
  });
}

function out(obj) {
  process.stdout.write(JSON.stringify(obj));
}

async function main() {
  const raw = await readStdin();
  let req;
  try {
    req = JSON.parse(raw || '{}');
  } catch (e) {
    out({ ok: false, error: 'invalid request JSON: ' + e.message, errorType: 'bad_request' });
    return;
  }
  if (!req.url) {
    out({ ok: false, error: 'missing url', errorType: 'bad_request' });
    return;
  }

  const { chromium } = loadPlaywright();

  // Resolve a Chromium executable: prefer the one Playwright was configured
  // with (PLAYWRIGHT_BROWSERS_PATH), else let Playwright resolve its bundled one.
  let executablePath;
  if (req.executablePath) {
    executablePath = req.executablePath;
  } else {
    try {
      const fs = require('fs');
      const base = process.env.PLAYWRIGHT_BROWSERS_PATH;
      if (base && fs.existsSync(base)) {
        const dir = fs.readdirSync(base)
          .filter((n) => /^chromium-\d+$/.test(n))
          .sort()
          .pop();
        if (dir) {
          const p = `${base}/${dir}/chrome-linux/chrome`;
          if (fs.existsSync(p)) executablePath = p;
        }
      }
    } catch (_) { /* fall back to Playwright's own resolution */ }
  }

  const proxy = req.proxy || process.env.HTTPS_PROXY || process.env.https_proxy || '';
  // Auto-enable the TLS 1.2 cap when going through a proxy (see header note),
  // unless the caller explicitly overrides via req.tls12.
  const tls12 = req.tls12 === undefined ? Boolean(proxy) : Boolean(req.tls12);

  const launchArgs = ['--no-sandbox', '--disable-dev-shm-usage'];
  if (tls12) launchArgs.push('--ssl-version-max=tls1.2');

  const launchOpts = {
    headless: true,
    args: launchArgs,
  };
  if (executablePath) launchOpts.executablePath = executablePath;
  if (proxy) launchOpts.proxy = { server: proxy };

  let browser;
  try {
    browser = await chromium.launch(launchOpts);
  } catch (e) {
    out({ ok: false, error: 'browser launch failed: ' + e.message, errorType: 'launch_failed' });
    return;
  }

  const timeoutMs = Number(req.timeoutMs) || 45000;
  // Hoisted so the catch block can still report a captured HTTP status.
  let mainStatus = 0;
  let mainHeaders = {};
  let page0 = null;
  try {
    const ctxOpts = {};
    if (req.userAgent) ctxOpts.userAgent = req.userAgent;
    if (req.extraHeaders && Object.keys(req.extraHeaders).length) {
      ctxOpts.extraHTTPHeaders = req.extraHeaders;
    }
    // Mirror the Python --insecure flag (default: verify TLS).
    if (req.insecure) ctxOpts.ignoreHTTPSErrors = true;
    const context = await browser.newContext(ctxOpts);
    const page = await context.newPage();
    page0 = page;

    // Record the main-frame response status as it arrives. Chromium throws
    // net::ERR_HTTP_RESPONSE_CODE_FAILURE from page.goto() for some empty-body
    // 4xx/5xx responses, which would otherwise hide the real status (403/429/
    // 503) the caller needs to classify and escalate correctly.
    page.on('response', (r) => {
      try {
        const req = r.request();
        if (req.isNavigationRequest() && r.frame() === page.mainFrame()) {
          mainStatus = r.status();      // last navigation response wins (handles redirects)
          mainHeaders = r.headers();
        }
      } catch (_) {}
    });

    // Optionally drop heavy sub-resources to fetch the document faster.
    if (req.blockResources) {
      await page.route('**/*', (route) => {
        const t = route.request().resourceType();
        if (t === 'image' || t === 'media' || t === 'font') return route.abort();
        return route.continue();
      });
    }

    const resp = await page.goto(req.url, {
      waitUntil: req.waitUntil || 'domcontentloaded',
      timeout: timeoutMs,
    });

    // Give client-rendered pages a brief settle window (best effort).
    try { await page.waitForLoadState('networkidle', { timeout: 4000 }); } catch (_) {}

    const status = resp ? resp.status() : 0;
    const finalUrl = page.url();
    const html = await page.content();
    let title = '';
    try { title = await page.title(); } catch (_) {}
    const headers = resp ? resp.headers() : {};

    let screenshotPath = null;
    if (req.screenshotPath) {
      await page.screenshot({ path: req.screenshotPath, fullPage: true });
      screenshotPath = req.screenshotPath;
    }

    out({
      ok: status > 0 && status < 400,
      status,
      finalUrl,
      title,
      html,
      headers,
      screenshotPath,
      tls12,
    });
  } catch (e) {
    const msg = (e && e.message) ? e.message.split('\n')[0] : String(e);
    // Surface the proxy-MITM TLS symptom explicitly so the caller can advise.
    let errorType = 'navigation_failed';
    if (/ERR_CONNECTION_CLOSED/.test(msg)) errorType = 'connection_closed';
    else if (/ERR_PROXY|ERR_TUNNEL/.test(msg)) errorType = 'proxy_error';
    else if (/Timeout|timeout/.test(msg)) errorType = 'timeout';
    // If we captured a main-frame HTTP status before goto threw (e.g. an
    // empty-body 403/503), report it as a real response so the caller can
    // classify/escalate instead of treating it as an opaque failure.
    if (typeof mainStatus !== 'undefined' && mainStatus >= 400) {
      out({ ok: false, status: mainStatus, finalUrl: (page0 && page0.url()) || req.url,
            headers: mainHeaders || {}, html: '', title: '',
            error: msg, errorType, tls12 });
    } else {
      out({ ok: false, error: msg, errorType, tls12 });
    }
  } finally {
    try { await browser.close(); } catch (_) {}
  }
}

main().catch((e) => {
  out({ ok: false, error: String(e && e.message || e), errorType: 'fatal' });
});
