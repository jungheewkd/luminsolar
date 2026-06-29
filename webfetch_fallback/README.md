# webfetch_fallback — 403 / 정책 차단 자료 스크래핑 도구

WebFetch가 가져오지 못하는 페이지(사이트의 **403 봇 차단** 또는 egress 프록시의 **443 정책
차단**)를 대신 가져오기 위한 폴백 스크래퍼입니다. 두 가지 실패는 성격이 완전히 다르므로 다르게
처리합니다.

| 실패 종류 | 원인 | 이 도구의 동작 |
|-----------|------|----------------|
| **사이트 403 / 429** | 대상 사이트의 봇 탐지(빈약한 User-Agent, 쿠키 없음, JS 전용 페이지) | **복구 시도** — 브라우저형 헤더 → `curl` → 실제 헤드리스 Chromium으로 단계적 상승(escalation) |
| **egress 정책 차단 (403/407)** | 회사/조직 정책상 프록시가 해당 호스트로의 터널을 거부 | **즉시 중단** — 우회하지 않고 차단된 호스트를 보고. allow-list 요청 필요 |

> **핵심 원칙:** 조직의 egress 정책(443 정책 차단)은 **우회하지 않습니다.** 프록시가 거부한
> 호스트는 감지해서 보고만 하고, 관리자에게 allow-list를 요청해야 합니다.

---

## How it works — the escalation ladder

```
http (requests)  →  curl  →  browser (headless Chromium)
   │  사이트 403 / 429 / 빈(JS) 응답이면 다음 단계로 상승
   │  egress 403 / 407 (정책 차단)이면 즉시 중단하고 보고 — 절대 우회하지 않음
```

- **Tier 1 — `requests`**: 현재 Chrome 헤더 세트, 쿠키 세션, gzip/br, 지수 백오프 + 지터 재시도,
  `Retry-After` 존중, 리다이렉트 추적. 대부분의 페이지는 여기서 끝납니다.
- **Tier 2 — `curl`**: 독립적인 TLS 스택. `requests`가 403을 받는 일부 사이트에서 성공하기도 합니다.
- **Tier 3 — 헤드리스 Chromium (Playwright)**: JavaScript를 실행하고 진짜 브라우저 지문을 보여주므로
  봇 차단 403을 가장 잘 통과하고 JS 렌더링 페이지도 가져옵니다.

## Environment / proxy notes (이 환경 자동 대응)

- 모든 HTTPS는 MITM egress 프록시(`$HTTPS_PROXY`)를 통과합니다. `requests`/`curl`/Chromium 모두
  환경변수(`REQUESTS_CA_BUNDLE` / `SSL_CERT_FILE`)의 CA 번들을 자동으로 신뢰합니다.
- **브라우저 TLS 1.2 캡:** 프록시 사용 시 브라우저 tier는 브라우저↔프록시 구간을
  `--ssl-version-max=tls1.2`로 제한합니다. Chromium 기본 TLS 1.3 ClientHello에는 포스트양자
  `X25519MLKEM768` key_share가 들어가 ClientHello가 ~1.8 KB로 커지는데, 프록시의 TLS 가로채기가
  이 큰 ClientHello에서 연결을 끊습니다(`ERR_CONNECTION_CLOSED`). TLS 1.2로 제한하면 해결됩니다.
  **오리진 보안 저하는 없습니다** — 오리진과의 실제 TLS는 브라우저가 아니라 프록시가 맺기 때문입니다.
  이 캡은 프록시가 있을 때만 자동 적용되므로, 프록시 없는 일반 PC에서는 정상 TLS 1.3로 동작합니다.

## Requirements

- **Python 3.9+** with `requests` (`pip install -r requirements.txt`).
- *(optional, for the browser tier)* **Node.js + Playwright + Chromium.** 이 원격 환경에는 이미
  설치되어 있습니다. 다른 곳에서는: `npm i playwright && npx playwright install chromium`.
- Node/Playwright/`curl`이 없어도 동작합니다(해당 tier만 비활성화되고 우아하게 강등).

## Usage

```bash
# 기본: 자동 escalation ladder (http → curl → browser)
python3 scrape.py https://example.com/page

# 여러 URL / 파일 입력, 출력 폴더 지정, 호스트당 1.5초 간격
python3 scrape.py -i urls.txt -o out/ --delay 1.5

# JS가 많은 페이지는 브라우저 우선 + 스크린샷
python3 scrape.py https://site/article --render --screenshot

# 특정 tier 강제
python3 scrape.py https://site --method browser     # auto|http|curl|browser
```

`urls.txt`는 한 줄에 URL 하나, `#`로 시작하는 줄은 주석입니다.

### 주요 옵션

| 옵션 | 설명 |
|------|------|
| `-m, --method auto\|http\|curl\|browser` | 기본 `auto`(escalation ladder) |
| `--render` | 브라우저 tier를 먼저 시도(JS 페이지) |
| `--screenshot` | 전체 페이지 스크린샷 저장(브라우저 tier) |
| `-o, --out DIR` | 출력 폴더(기본 `scraped/`) |
| `--timeout SEC` | 요청당 타임아웃(기본 30) |
| `--max-retries N` | tier별 재시도 횟수(기본 2) |
| `--delay SEC` | 동일 호스트 요청 간 최소 간격(기본 1.0) — 예의 |
| `--concurrency N` | 병렬 워커 수(기본 4) |
| `-A, --user-agent UA` / `-H "Key: Value"` | UA / 추가 헤더 |
| `--proxy URL` / `--no-proxy` | 프록시 명시 / 무시 |
| `--cacert FILE` / `--insecure` | CA 번들 / TLS 검증 끄기(비권장) |
| `--respect-robots` | robots.txt 준수(차단 URL 건너뜀) |
| `--save-failures` | 실패한 응답 본문도 저장 |

### Output

출력 폴더에:
- `<name>.html` / `.json` / `.xml` — 원본 본문
- `<name>.txt` — 추출한 텍스트(미리보기/인덱싱용)
- `<name>.png` — 스크린샷(`--screenshot` 사용 시)
- `<name>.meta.json` — URL별 메타데이터(상태, 최종 URL, 사용 tier, 분류)
- `results.json` — 전체 실행 매니페스트

### Exit codes

| 코드 | 의미 |
|------|------|
| `0` | 모두 성공 |
| `2` | 일부 실패(사이트 403/네트워크 등) |
| `3` | **egress 정책 차단 호스트 있음** — allow-list 필요(스크래핑 문제가 아님) |
| `4` | 잘못된 호출 |

## Responsible use / 책임 있는 사용

- 본인이 **접근 권한이 있는** 자료만 수집하세요. 이 도구는 조직의 egress 정책을 **우회하지 않습니다.**
- `--delay`로 예의를 지키고, 필요 시 `--respect-robots`로 robots.txt를 준수하세요.
- 각 사이트의 이용약관과 관련 법령 준수는 사용자 책임입니다.
