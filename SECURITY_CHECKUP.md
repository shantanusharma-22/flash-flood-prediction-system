# SECURITY_CHECKUP.md — NDRF Flash Flood & Landslide Early Warning System

**Audit date:** 2026-10-06
**Stack:** FastAPI (Python 3.12) + single-page HTML5 / Tailwind CDN / Leaflet / Chart.js frontend at `app/static/`
**Result:** PASS — 29/29 tests green, CSP/HSTS live, no known dependency CVEs, XSS vectors neutralised.

---

## 1. SECURITY POSTURE SUMMARY

| Area | Status |
|---|---|
| Content-Security-Policy (CSP) | ✅ Strict `script-src`/`style-src`/`img-src`/`connect-src`, `base-uri`, `object-src none`, `frame-ancestors none`, `form-action self` |
| HSTS | ✅ `max-age=31536000; includeSubDomains` on HTML (not on API, to avoid breaking non-browser clients) |
| X-Frame-Options / anti-clickjacking | ✅ `DENY` |
| X-Content-Type-Options | ✅ `nosniff` |
| Referrer-Policy | ✅ `no-referrer` |
| Permissions-Policy | ✅ scopes only the capabilities the app needs (geolocation, camera, microphone, payment, USB) |
| Cross-origin isolation | ✅ COOP=`same-origin`, CORP=`same-origin`, `X-Permitted-Cross-Domain-Policies: none` |
| Cache hygiene | ✅ `Cache-Control: no-store` on `/api/*`; service worker caches the same-origin shell only, never `/api/*` or `/ws/*` |
| Input validation | ✅ Pydantic `allow_inf_nan=False`, `Path(pattern=...)`, `Literal`, `Field(min/max)` on every route that takes user input |
| Rate limiting | ✅ 60s sliding-window limiter (configurable via `RATE_LIMIT_MAX_MUTATIONS`, default 300) on POST/PUT/PATCH/DELETE |
| WebSocket origin check | ✅ `/ws/telemetry` rejects foreign `Origin` (close 1008 = policy violation) |
| XSS hardening | ✅ `esc()` on every server- and user-supplied value rendered into the DOM; no inline `onclick` handlers remain; triage buttons bound via `addEventListener` |
| Dependency vulnerabilities | ✅ `pip-audit -r requirements.txt` → no known vulnerabilities |
| Test coverage | ✅ 29/29 tests green, including the new security regression suite |

---

## 2. FINDINGS & FIXES APPLIED THIS SESSION

### 2.1 NaN payloads crashed FastAPI default validation (500 → 422)
**Finding:** A request containing a non-finite float (e.g. `NaN` in a `predict` payload) raised FastAPI's default validation exception, returning **HTTP 500** instead of **422**.
**Fix:** Added a `RequestValidationError` handler that JSON-serialises non-finite floats via `_json_safe()`, so invalid numeric input now surfaces as a clean **422**.

### 2.2 Frontend HTML escaping
**Finding:** User- and server-supplied values rendered into `innerHTML` were direct injection sinks.
**Fix:** Added `esc()` in `app/static/app.js`. Every interpolated value in ward cards, map popups, the sensor table, historical table, chat bubbles, SOS rows, and the SOS triage button labels is now passed through `esc()`. SOS triage buttons were re-bound with `addEventListener` (no inline `onclick`). The only remaining interpolation in the chat path is escaped: `esc(data.reply)` and `esc(msg)`.

### 2.3 Floating `@latest` / unpinned CDN references
**Finding:** Earlier extraction left `@latest`-tagged CDN URLs that were hard to pin and broke strict script-src CSP.
**Fix:** Tailwind 3.4.16, Leaflet 1.9.4, Chart.js 4.5.1, and Lucide 1.52.0 are pinned; `integrity` + `crossorigin="anonymous"` are set on every third-party script. Leaflet CSS/JS and Lucide theming require `style-src` entries for `https://unpkg.com` and `https://cdn.jsdelivr.net`, which are included alongside `'self'` and Google Fonts.

### 2.4 Service worker cache-first on the shell only
**Finding:** An aggressive cache-first worker could serve stale telemetry and could retain SOS/dispatch payloads in a shared browser cache.
**Fix:** Cache-first only on the same-origin shell (`/`, `/manifest.json`, `/static/app.js`, `/static/tailwind-config.js`). `/api/*` and `/ws/*` are never cached (network-first path). Same-origin-only fetching, plus `skipWaiting()`/`clients.claim()` guarantees activation.

### 2.5 Favicon 404 eliminated
**Finding:** No favicon existed; the browser fired a 404 for the favicon on every load.
**Fix:** `app/static/favicon.svg` added and referenced from `<link rel="icon">` in `index.html`.

### 2.6 Docs disabled via toggle
**Finding:** FastAPI's interactive docs were always enabled.
**Fix:** `docs_url`, `/redoc`, and `/openapi.json` are set to `None` when `DISABLE_DOCS=1`.

---

## 3. LIVE SMOKE TEST (fresh server boot, 2026-10-06)

- `GET /api/health` → **200**, `{"status":"HEALTHY",...}`
- `GET /` → **200**, CSP + HSTS present; favicon/app.js/manifest/sw fetch with **200**
- Invalid scenario → **422**; bad SOS status → **422**; random ward → **404**; `NaN` predict → **422**
- Valid SOS status + AI chat + AI advisory → **200**
- Rate limiter defaults: POST `/api/wards` → **405** (non-mutating route correctly excluded); POST to `/api/ai-chat` → **200**
- `pip-audit -r requirements.txt` → "No known vulnerabilities found"
- `python -m pytest -q` → **29 passed** (17 endpoints/physics/risk + 12 security regression)

---

## 4. DEPLOYMENT CAVEATS

1. **Tailwind CDN warning** — `cdn.tailwindcss.com` is still loaded at runtime for the utility layer. The project is structured for a build step that compiles to static CSS, which would let `script-src 'self'` and `style-src 'self'` run without any CDN. Until then, the CDN scripts are pinned and SRI-locked.
2. **HSTS only on HTML** — The `Strict-Transport-Security` header is set on the HTML shell, not on `/api/*`, so API clients and non-browser tooling do not get unexpectedly downgraded or blocked.
3. **Rate-limit tuning** — `RATE_LIMIT_MAX_MUTATIONS` (default 300/60s) governs POST/PUT/PATCH/DELETE. If the simulator, dispatch, or AI flows are exercised heavily in production, raise the value or reduce the window.
4. **Docs toggle** — Set `DISABLE_DOCS=1` in production to hide the interactive OpenAPI surface.
5. **AI advisory** — `gemini_advisor.py` may return an expert fallback when the real Gemini call fails; verify the POC keys and the expert fallback in `tests/test_security.py` match your deployment.
6. **Telemetry** — The WebSocket `/ws/telemetry` closes with **1008** on a foreign `Origin` (policy violation), so always connect from the same host as the page.
