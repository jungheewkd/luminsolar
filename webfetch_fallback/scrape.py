#!/usr/bin/env python3
"""
scrape.py - a resilient fallback fetcher for pages the built-in WebFetch can't get.

WHY THIS EXISTS
---------------
WebFetch can fail for two very different reasons that need very different handling:

  1. SITE-level 403 / 429 ("403 차단")
       The *target website* refuses a bare HTTP client - bot detection, a
       missing/Ë‘plain User-Agent, no cookies, or content that only appears after
       JavaScript runs. This IS recoverable: send realistic browser headers,
       keep a cookie session, back off and retry, and finally fall back to a
       real headless browser that executes JS and looks like Chrome.

  2. PROXY / egress-policy block ("443 정책 차단")
       The *egress proxy* (this environment routes all HTTPS through one) refuses
       to open a tunnel to the host - the destination is not on your
       organization's allow-list. The proxy answers the CONNECT with 403/407.
       This is NOT recoverable by retrying or changing headers, and the proxy
       README is explicit: do not route around it. This script DETECTS that
       case, STOPS immediately, and reports the blocked host so you can ask for
       it to be allow-listed.

So the tool is an *escalation ladder* that also knows when to stop:

    http (requests)  ->  curl (different TLS stack)  ->  browser (Chromium)
         |  on a site 403/429/empty/JS page, climb to the next rung
         |  on a proxy/egress 403/407, STOP and report - never bypass policy

ENVIRONMENT NOTES (auto-detected)
---------------------------------
* HTTPS_PROXY and the CA bundle (REQUESTS_CA_BUNDLE / SSL_CERT_FILE) are read
  from the environment, so requests/curl/Chromium all trust the proxy CA.
* The browser tier caps the browser<->proxy hop at TLS 1.2 when a proxy is in
  use. The proxy's TLS interception closes the oversized post-quantum TLS 1.3
  ClientHello that Chromium sends by default; capping at 1.2 fixes it with no
  security loss to the origin (the proxy, not the browser, talks TLS to the
  origin). See browser_fetch.cjs for the full explanation.

RESPONSIBLE USE
---------------
Only scrape content you are authorized to access. This tool deliberately does
NOT attempt to defeat your organization's egress policy. Use --respect-robots
to honor robots.txt, and --delay to stay polite. You are responsible for
complying with each site's terms of service and applicable law.

USAGE
-----
    python3 scrape.py https://example.com/page
    python3 scrape.py -i urls.txt -o out/ --method auto --delay 1.5
    python3 scrape.py https://site/article --render --screenshot
    python3 scrape.py https://site --method browser   # force the browser tier

Exit codes: 0 all ok, 2 some failed, 3 a host was blocked by egress policy,
4 bad invocation.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict, field
from html.parser import HTMLParser
from pathlib import Path
from threading import Lock
from urllib.parse import urlparse
from urllib import robotparser

try:
    import requests
except ImportError:
    sys.stderr.write(
        "ERROR: the 'requests' package is required. Install it with:\n"
        "       python3 -m pip install requests\n"
    )
    sys.exit(4)


# --------------------------------------------------------------------------- #
# Classifications - the result categories that drive escalate-vs-stop logic.
# --------------------------------------------------------------------------- #
OK = "ok"
SITE_FORBIDDEN = "site_forbidden"       # HTTP 403 from the site -> escalate
RATE_LIMITED = "rate_limited"           # HTTP 429/503 -> honor Retry-After, retry
NOT_FOUND = "not_found"                 # HTTP 404/410 -> do not escalate
SERVER_ERROR = "server_error"           # HTTP 5xx -> limited retry
EMPTY_OR_JS = "empty_or_js"             # 200 but no usable content -> try browser
POLICY_BLOCKED = "policy_blocked"       # proxy/egress 403/407 -> STOP, report
NETWORK_ERROR = "network_error"         # DNS/conn/timeout -> escalate/retry
BLOCKED_OTHER = "blocked_other"         # other 4xx -> report

# A realistic, current Chrome-on-Linux header set. The single biggest fix for
# site-level 403s is simply not looking like a scripted client.
DEFAULT_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
)
BROWSER_HEADERS = {
    "User-Agent": DEFAULT_UA,
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9,ko;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Ch-Ua": '"Chromium";v="141", "Not?A_Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Linux"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "Connection": "keep-alive",
}

HERE = Path(__file__).resolve().parent
BROWSER_HELPER = HERE / "browser_fetch.cjs"
PROXY_STATUS_URL = "http://127.0.0.1:45069/__agentproxy/status"


@dataclass
class FetchOutcome:
    """Outcome of a single tier attempt."""
    classification: str
    status: int = 0
    final_url: str = ""
    headers: dict = field(default_factory=dict)
    body: bytes = b""
    text: str = ""
    title: str = ""
    tier: str = ""
    detail: str = ""
    screenshot_path: str = ""

    @property
    def ok(self) -> bool:
        return self.classification == OK


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
class _TextExtractor(HTMLParser):
    """Dependency-free HTML -> text. Good enough for previews/indexing."""
    _SKIP = {"script", "style", "noscript", "template", "svg"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1
        elif tag in ("br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4"):
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0 and data.strip():
            self._parts.append(data)

    def text(self) -> str:
        raw = "".join(self._parts)
        return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", raw)).strip()


def html_to_text(html: str) -> str:
    try:
        p = _TextExtractor()
        p.feed(html)
        return p.text()
    except Exception:
        return re.sub(r"<[^>]+>", " ", html)


def looks_empty_or_js(html: str) -> bool:
    """Heuristic: a 200 that is really a JS shell with no readable content."""
    text = html_to_text(html or "")
    if len(text) >= 500:
        return False
    low = (html or "").lower()
    js_markers = ("enable javascript", "__next_data__", "id=\"root\"",
                  "id=\"app\"", "window.__nuxt__", "data-reactroot")
    return any(m in low for m in js_markers) or len(text) < 80


def proxy_block_reason(host: str) -> str:
    """Ask the agent proxy why a host was refused (best effort)."""
    try:
        r = requests.get(PROXY_STATUS_URL, timeout=4)
        data = r.json()
        for f in data.get("recentRelayFailures", []) or []:
            if host and host in json.dumps(f):
                return json.dumps(f)
    except Exception:
        pass
    return ""


def is_proxy_denial(message: str) -> bool:
    """True if an error message indicates the EGRESS PROXY refused the tunnel."""
    m = (message or "").lower()
    return (
        "tunnel connection failed" in m
        or "received http code 403 from proxy" in m
        or "received http code 407 from proxy" in m
        or ("407" in m and "proxy" in m)
        or "proxy authentication required" in m
    )


# --------------------------------------------------------------------------- #
# Tier 1: requests
# --------------------------------------------------------------------------- #
def fetch_requests(url, session, timeout, headers, verify, allow_redirects=True) -> FetchOutcome:
    try:
        r = session.get(url, timeout=timeout, headers=headers,
                        allow_redirects=allow_redirects, verify=verify)
    except requests.exceptions.ProxyError as e:
        msg = str(e)
        if is_proxy_denial(msg):
            host = urlparse(url).hostname or ""
            reason = proxy_block_reason(host)
            return FetchOutcome(POLICY_BLOCKED, tier="http",
                                detail=f"egress proxy refused tunnel to {host}. {reason}".strip())
        return FetchOutcome(NETWORK_ERROR, tier="http", detail=f"proxy error: {msg}")
    except requests.exceptions.SSLError as e:
        return FetchOutcome(NETWORK_ERROR, tier="http", detail=f"TLS error: {e}")
    except (requests.exceptions.ConnectionError,
            requests.exceptions.Timeout) as e:
        # A proxy denial sometimes surfaces as a ConnectionError too.
        if is_proxy_denial(str(e)):
            host = urlparse(url).hostname or ""
            return FetchOutcome(POLICY_BLOCKED, tier="http",
                                detail=f"egress proxy refused tunnel to {host}. {proxy_block_reason(host)}".strip())
        return FetchOutcome(NETWORK_ERROR, tier="http", detail=f"{type(e).__name__}: {e}")
    except requests.exceptions.RequestException as e:
        return FetchOutcome(NETWORK_ERROR, tier="http", detail=f"{type(e).__name__}: {e}")

    body = r.content
    text = ""
    ctype = r.headers.get("Content-Type", "")
    if "text" in ctype or "html" in ctype or "json" in ctype or "xml" in ctype:
        text = html_to_text(r.text) if "html" in ctype else r.text

    cls = _classify_status(r.status_code, r.headers, r.text if "html" in ctype else "")
    return FetchOutcome(cls, status=r.status_code, final_url=r.url,
                        headers=dict(r.headers), body=body, text=text,
                        tier="http", detail=r.headers.get("Retry-After", ""))


def _classify_status(status: int, headers: dict, html: str) -> str:
    if 200 <= status < 300:
        if html and looks_empty_or_js(html):
            return EMPTY_OR_JS
        return OK
    if status == 403:
        return SITE_FORBIDDEN
    if status in (429, 503):
        return RATE_LIMITED
    if status in (404, 410):
        return NOT_FOUND
    if 500 <= status < 600:
        return SERVER_ERROR
    if 300 <= status < 400:
        return OK  # redirects are followed; a bare 3xx here is fine
    return BLOCKED_OTHER


# --------------------------------------------------------------------------- #
# Tier 2: curl (independent TLS stack; sometimes succeeds where requests 403s)
# --------------------------------------------------------------------------- #
def fetch_curl(url, timeout, headers, proxy, cabundle) -> FetchOutcome:
    hdr_args = []
    for k, v in headers.items():
        hdr_args += ["-H", f"{k}: {v}"]
    cmd = ["curl", "-sS", "-L", "--compressed",
           "--max-time", str(int(timeout)),
           "-w", "\n__HTTP_STATUS__%{http_code}__FINAL__%{url_effective}__",
           *hdr_args, url]
    if proxy:
        cmd += ["--proxy", proxy]
    if cabundle:
        cmd += ["--cacert", cabundle]
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout + 10)
    except subprocess.TimeoutExpired:
        return FetchOutcome(NETWORK_ERROR, tier="curl", detail="curl timed out")
    except FileNotFoundError:
        return FetchOutcome(NETWORK_ERROR, tier="curl", detail="curl not installed")

    stderr = p.stderr.decode("utf-8", "replace")
    if p.returncode != 0:
        if is_proxy_denial(stderr):
            host = urlparse(url).hostname or ""
            return FetchOutcome(POLICY_BLOCKED, tier="curl",
                                detail=f"egress proxy refused tunnel to {host}. {stderr.strip()}")
        return FetchOutcome(NETWORK_ERROR, tier="curl", detail=stderr.strip()[:300])

    raw = p.stdout
    m = re.search(rb"\n__HTTP_STATUS__(\d+)__FINAL__(.*?)__\s*$", raw, re.S)
    status, final_url = 0, url
    if m:
        status = int(m.group(1))
        final_url = m.group(2).decode("utf-8", "replace")
        raw = raw[:m.start()]
    html = raw.decode("utf-8", "replace")
    cls = _classify_status(status, {}, html)
    return FetchOutcome(cls, status=status, final_url=final_url, body=raw,
                        text=html_to_text(html), tier="curl")


# --------------------------------------------------------------------------- #
# Tier 3: headless Chromium (executes JS, real browser fingerprint)
# --------------------------------------------------------------------------- #
def fetch_browser(url, timeout, headers, ua, proxy, screenshot_path=None) -> FetchOutcome:
    if not BROWSER_HELPER.exists():
        return FetchOutcome(NETWORK_ERROR, tier="browser",
                            detail=f"helper not found: {BROWSER_HELPER}")
    node = _which_node()
    if not node:
        return FetchOutcome(NETWORK_ERROR, tier="browser",
                            detail="node not found; cannot use the browser tier")

    extra = {k: v for k, v in headers.items()
            if k.lower() not in ("user-agent", "accept-encoding", "connection",
                                 "host", "content-length")}
    req = {
        "url": url,
        "timeoutMs": int(timeout * 1000),
        "userAgent": ua,
        "extraHeaders": extra,
        "proxy": proxy or "",
        "waitUntil": "domcontentloaded",
    }
    if screenshot_path:
        req["screenshotPath"] = screenshot_path

    env = dict(os.environ)
    # Let the helper find a globally-installed playwright if needed.
    groot = "/opt/node22/lib/node_modules"
    env["NODE_PATH"] = (env.get("NODE_PATH", "") + os.pathsep + groot).strip(os.pathsep)
    try:
        p = subprocess.run([node, str(BROWSER_HELPER)],
                        input=json.dumps(req).encode(),
                        capture_output=True, timeout=timeout + 30, env=env)
    except subprocess.TimeoutExpired:
        return FetchOutcome(NETWORK_ERROR, tier="browser", detail="browser timed out")

    if p.returncode != 0 and not p.stdout.strip():
        return FetchOutcome(NETWORK_ERROR, tier="browser",
                            detail=p.stderr.decode("utf-8", "replace")[:300])
    try:
        res = json.loads(p.stdout.decode("utf-8", "replace"))
    except json.JSONDecodeError:
        return FetchOutcome(NETWORK_ERROR, tier="browser",
                            detail="unparseable browser output: "
                                   + p.stdout.decode("utf-8", "replace")[:200])

    if res.get("error"):
        etype = res.get("errorType", "")
        detail = res["error"]
        # If the navigation failed but we still captured a real HTTP status
        # (e.g. an empty-body 403/429/503), classify by that status so the
        # ladder treats it like the http/curl tiers do.
        st = int(res.get("status") or 0)
        if st >= 400:
            cls = _classify_status(st, res.get("headers", {}), res.get("html", "") or "")
            return FetchOutcome(cls, status=st, final_url=res.get("finalUrl", url),
                                headers=res.get("headers", {}), tier="browser",
                                detail=f"{etype}: {detail}")
        # A connection-closed through the proxy usually means the TLS cap was
        # not applied or the host is unreachable; surface it clearly.
        cls = NETWORK_ERROR
        if etype == "proxy_error" and is_proxy_denial(detail):
            cls = POLICY_BLOCKED
        return FetchOutcome(cls, tier="browser", detail=f"{etype}: {detail}")

    status = int(res.get("status") or 0)
    html = res.get("html", "") or ""
    cls = _classify_status(status, res.get("headers", {}), html)
    return FetchOutcome(cls, status=status, final_url=res.get("finalUrl", url),
                        headers=res.get("headers", {}),
                        body=html.encode("utf-8", "replace"),
                        text=html_to_text(html), title=res.get("title", ""),
                        tier="browser", screenshot_path=res.get("screenshotPath") or "")


def _which_node():
    for n in ("node", "/opt/node22/bin/node", "/usr/local/bin/node", "/usr/bin/node"):
        try:
            subprocess.run([n, "--version"], capture_output=True, timeout=8, check=True)
            return n
        except Exception:
            continue
    return None


# --------------------------------------------------------------------------- #
# Orchestration: per-URL escalation ladder with retries + politeness
# --------------------------------------------------------------------------- #
class DomainThrottle:
    """Enforces a minimum interval between requests to the same host."""
    def __init__(self, min_interval: float):
        self.min_interval = min_interval
        self._last: dict[str, float] = {}
        self._lock = Lock()

    def wait(self, host: str):
        if self.min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            last = self._last.get(host, 0.0)
            sleep_for = self.min_interval - (now - last)
            if sleep_for > 0:
                time.sleep(sleep_for)
            self._last[host] = time.monotonic()


def robots_allows(url: str, ua: str) -> bool:
    parts = urlparse(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    rp = robotparser.RobotFileParser()
    try:
        # Fetch robots.txt through the same proxy/CA as everything else.
        r = requests.get(robots_url, timeout=10, headers={"User-Agent": ua})
        if r.status_code >= 400:
            return True  # no robots or inaccessible -> not disallowed
        rp.parse(r.text.splitlines())
        return rp.can_fetch(ua, url)
    except Exception:
        return True


def scrape_one(url, cfg, throttle: DomainThrottle) -> dict:
    host = urlparse(url).hostname or ""
    if cfg.respect_robots and not robots_allows(url, cfg.user_agent):
        return _record(url, FetchOutcome(BLOCKED_OTHER, tier="robots",
                                        detail="disallowed by robots.txt"), cfg)

    session = requests.Session()
    headers = dict(BROWSER_HEADERS)
    headers["User-Agent"] = cfg.user_agent
    headers.update(cfg.extra_headers)

    # Tiers to try, in order. Honor an explicit --method.
    if cfg.method == "http":
        ladder = ["http"]
    elif cfg.method == "curl":
        ladder = ["curl"]
    elif cfg.method == "browser":
        ladder = ["browser"]
    else:  # auto
        ladder = ["http", "curl", "browser"]
        if cfg.render:
            ladder = ["browser", "http", "curl"]

    last: FetchOutcome | None = None
    for tier in ladder:
        throttle.wait(host)
        outcome = _attempt_with_retries(url, tier, session, headers, cfg)
        last = outcome

        if outcome.classification == POLICY_BLOCKED:
            # HARD STOP. Egress policy is not something we work around.
            return _record(url, outcome, cfg, policy_blocked=True)
        if outcome.ok:
            return _record(url, outcome, cfg)
        if outcome.classification in (NOT_FOUND,):
            return _record(url, outcome, cfg)
        # Otherwise (site 403, 429 exhausted, 5xx, empty/JS, network): escalate.
        sys.stderr.write(
            f"  [{tier}] {url} -> {outcome.classification}"
            f"{' ('+str(outcome.status)+')' if outcome.status else ''}"
            f"{' - '+outcome.detail if outcome.detail else ''}; escalating...\n"
        )

    return _record(url, last or FetchOutcome(NETWORK_ERROR), cfg)


def _attempt_with_retries(url, tier, session, headers, cfg) -> FetchOutcome:
    attempts = cfg.max_retries + 1
    outcome = FetchOutcome(NETWORK_ERROR)
    for i in range(attempts):
        if tier == "http":
            outcome = fetch_requests(url, session, cfg.timeout, headers, cfg.verify)
        elif tier == "curl":
            outcome = fetch_curl(url, cfg.timeout, headers, cfg.proxy, cfg.cabundle)
        else:
            ss = None
            if cfg.screenshot:
                ss = str(cfg.outdir / (_safe_name(url) + ".png"))
            outcome = fetch_browser(url, cfg.timeout, headers, cfg.user_agent,
                                    cfg.proxy, ss)

        # Never retry an egress-policy denial.
        if outcome.classification == POLICY_BLOCKED:
            return outcome
        if outcome.ok or outcome.classification in (NOT_FOUND, SITE_FORBIDDEN, EMPTY_OR_JS):
            # site_forbidden/empty: no point hammering the same tier; escalate.
            if outcome.classification in (SITE_FORBIDDEN, EMPTY_OR_JS) and i == 0:
                return outcome
            if outcome.ok or outcome.classification == NOT_FOUND:
                return outcome

        if i < attempts - 1:
            delay = _backoff(i, outcome, cfg)
            sys.stderr.write(f"  [{tier}] retry {i+1}/{cfg.max_retries} in {delay:.1f}s\n")
            time.sleep(delay)
    return outcome


def _backoff(i, outcome: FetchOutcome, cfg) -> float:
    # Honor Retry-After on 429/503 when present.
    if outcome.classification == RATE_LIMITED and outcome.detail:
        try:
            return min(float(outcome.detail), 120.0)
        except ValueError:
            pass
    base = cfg.backoff_base * (2 ** i)
    return min(base + random.uniform(0, base * 0.3), 60.0)


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
def _safe_name(url: str) -> str:
    p = urlparse(url)
    name = (p.netloc + p.path).strip("/").replace("/", "_") or p.netloc or "index"
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)[:120]
    if p.query:
        name += "_" + re.sub(r"[^A-Za-z0-9]", "", p.query)[:24]
    return name or "page"


def _record(url, outcome: FetchOutcome, cfg, policy_blocked=False) -> dict:
    rec = {
        "url": url,
        "ok": outcome.ok,
        "classification": outcome.classification,
        "status": outcome.status,
        "final_url": outcome.final_url,
        "tier": outcome.tier,
        "detail": outcome.detail,
        "title": outcome.title,
        "policy_blocked": policy_blocked,
        "bytes": len(outcome.body),
    }
    if outcome.body and (outcome.ok or cfg.save_failures):
        base = cfg.outdir / _safe_name(url)
        ext = ".html"
        ctype = (outcome.headers or {}).get("Content-Type", "")
        if "json" in ctype:
            ext = ".json"
        elif "xml" in ctype:
            ext = ".xml"
        content_path = base.with_suffix(ext)
        content_path.write_bytes(outcome.body)
        rec["content_path"] = str(content_path)
        if outcome.text:
            text_path = base.with_suffix(".txt")
            text_path.write_text(outcome.text, encoding="utf-8")
            rec["text_path"] = str(text_path)
    if outcome.screenshot_path:
        rec["screenshot_path"] = outcome.screenshot_path
    # Sidecar metadata for every URL.
    meta_path = cfg.outdir / (_safe_name(url) + ".meta.json")
    meta_path.write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
    rec["meta_path"] = str(meta_path)
    return rec


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
@dataclass
class Config:
    method: str
    outdir: Path
    timeout: float
    max_retries: int
    backoff_base: float
    delay: float
    concurrency: int
    user_agent: str
    extra_headers: dict
    proxy: str
    cabundle: str
    verify: object
    render: bool
    screenshot: bool
    respect_robots: bool
    save_failures: bool


def build_config(args) -> Config:
    proxy = "" if args.no_proxy else (
        args.proxy or os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or "")
    cabundle = (args.cacert or os.environ.get("REQUESTS_CA_BUNDLE")
                or os.environ.get("SSL_CERT_FILE") or os.environ.get("CURL_CA_BUNDLE") or "")
    verify = cabundle if cabundle else True
    if args.insecure:
        verify = False
    extra_headers = {}
    for h in args.header or []:
        if ":" in h:
            k, v = h.split(":", 1)
            extra_headers[k.strip()] = v.strip()
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    # requests reads HTTPS_PROXY from env automatically; when --proxy is given
    # explicitly (or env is unset and we computed one) push it into the env so
    # the Session and curl/browser tiers all agree.
    if proxy:
        os.environ["HTTPS_PROXY"] = proxy
        os.environ.setdefault("https_proxy", proxy)
    elif args.no_proxy:
        os.environ.pop("HTTPS_PROXY", None)
        os.environ.pop("https_proxy", None)

    return Config(
        method=args.method, outdir=outdir, timeout=args.timeout,
        max_retries=args.max_retries, backoff_base=args.backoff_base,
        delay=args.delay, concurrency=args.concurrency,
        user_agent=args.user_agent or DEFAULT_UA, extra_headers=extra_headers,
        proxy=proxy, cabundle=cabundle, verify=verify, render=args.render,
        screenshot=args.screenshot, respect_robots=args.respect_robots,
        save_failures=args.save_failures,
    )


def collect_urls(args) -> list[str]:
    urls = list(args.urls)
    if args.input:
        for line in Path(args.input).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
    # de-dup, keep order
    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Resilient fallback fetcher for WebFetch 403 / egress-policy-blocked pages.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("USAGE")[0])
    ap.add_argument("urls", nargs="*", help="one or more URLs")
    ap.add_argument("-i", "--input", help="file with one URL per line (# comments allowed)")
    ap.add_argument("-o", "--out", default="scraped", help="output directory (default: scraped)")
    ap.add_argument("-m", "--method", default="auto",
                    choices=["auto", "http", "curl", "browser"],
                    help="auto = http->curl->browser escalation ladder (default)")
    ap.add_argument("--render", action="store_true",
                    help="prefer the headless browser first (for JS-heavy pages)")
    ap.add_argument("--screenshot", action="store_true", help="save a full-page screenshot (browser tier)")
    ap.add_argument("--timeout", type=float, default=30.0, help="per-request timeout seconds (default 30)")
    ap.add_argument("--max-retries", type=int, default=2, help="retries per tier (default 2)")
    ap.add_argument("--backoff-base", type=float, default=1.5, help="base seconds for exponential backoff")
    ap.add_argument("--delay", type=float, default=1.0, help="min seconds between requests to the same host")
    ap.add_argument("--concurrency", type=int, default=4, help="parallel workers across hosts (default 4)")
    ap.add_argument("-A", "--user-agent", help="override the User-Agent")
    ap.add_argument("-H", "--header", action="append", help="extra 'Key: Value' header (repeatable)")
    ap.add_argument("--proxy", help="explicit HTTPS proxy (default: $HTTPS_PROXY)")
    ap.add_argument("--no-proxy", action="store_true", help="ignore any environment proxy")
    ap.add_argument("--cacert", help="CA bundle (default: $REQUESTS_CA_BUNDLE / $SSL_CERT_FILE)")
    ap.add_argument("--insecure", action="store_true", help="disable TLS verification (NOT recommended)")
    ap.add_argument("--respect-robots", action="store_true", help="honor robots.txt (skip disallowed URLs)")
    ap.add_argument("--save-failures", action="store_true", help="also save bodies of failed responses")
    args = ap.parse_args(argv)

    urls = collect_urls(args)
    if not urls:
        ap.error("no URLs given (pass URLs or --input FILE)")
    cfg = build_config(args)

    sys.stderr.write(
        f"Fetching {len(urls)} URL(s) | method={cfg.method} "
        f"proxy={'on' if cfg.proxy else 'off'} out={cfg.outdir}\n"
    )
    throttle = DomainThrottle(cfg.delay)
    results = []
    workers = max(1, min(cfg.concurrency, len(urls)))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(scrape_one, u, cfg, throttle): u for u in urls}
        for fut in as_completed(futs):
            u = futs[fut]
            try:
                rec = fut.result()
            except Exception as e:
                rec = {"url": u, "ok": False, "classification": NETWORK_ERROR,
                       "detail": f"unhandled: {e}"}
            results.append(rec)
            _print_line(rec)

    # Summary + manifest
    manifest = cfg.outdir / "results.json"
    manifest.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    ok = sum(1 for r in results if r.get("ok"))
    blocked = [r for r in results if r.get("policy_blocked")]
    failed = [r for r in results if not r.get("ok") and not r.get("policy_blocked")]
    sys.stderr.write(f"\nDone: {ok} ok, {len(failed)} failed, {len(blocked)} egress-blocked. "
                     f"Manifest: {manifest}\n")
    if blocked:
        sys.stderr.write(
            "\nEGRESS-POLICY BLOCKED (not a scraping problem - the proxy refuses these hosts;\n"
            "ask your admin to allow-list them, do NOT try to bypass):\n")
        for r in blocked:
            sys.stderr.write(f"  - {urlparse(r['url']).hostname}  {r.get('detail','')}\n")

    if blocked:
        return 3
    if failed:
        return 2
    return 0


def _print_line(rec):
    mark = "OK " if rec.get("ok") else ("POL" if rec.get("policy_blocked") else "ERR")
    where = rec.get("content_path") or rec.get("detail") or rec.get("classification")
    via = f" via {rec.get('tier')}" if rec.get("tier") else ""
    status = f" {rec.get('status')}" if rec.get("status") else ""
    print(f"[{mark}]{status}{via}  {rec['url']}  ->  {where}")


if __name__ == "__main__":
    sys.exit(main())
