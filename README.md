# JARVIS AI — read-only market monitor

A small FastAPI service that runs in the cloud while your laptop is off. It polls Delta Exchange **public** product and OHLC candle endpoints, estimates swing support/resistance from completed candles, detects candle-close-confirmed breakouts/breakdowns, stores deduplicated alerts in SQLite, and can send iPhone push notifications through ntfy. It does **not** place, edit, or cancel orders.

## Included now

- Delta Exchange India public product list and OHLC candle polling (`/v2/products`, `/v2/history/candles`). Delta documents these public endpoints and the available candle resolutions at <https://docs.delta.exchange/>.
- Polling of configured symbols and one configured timeframe; current/incomplete candles are excluded before analysis.
- Pivot-based support/resistance estimates; approach alerts and breakout/breakdown alerts only after a completed candle closes through a level. A wick alone does not confirm a breakout.
- SQLite alert history and persistent deduplication. Approach alerts are grouped into cooldown buckets; confirmed breakouts/breakdowns are deduplicated per symbol/timeframe/level/candle.
- ntfy notifications compatible with the ntfy iOS app, plus optional HTTPS webhook.
- Dashboard and authenticated APIs, RSS news polling, health endpoint.
- Private Delta positions remain disabled and unimplemented until current regional API authentication/signing is independently verified. No order-placement endpoint exists.

## Important limitations

- Support/resistance is a transparent heuristic, not a promise of market behavior or a recommendation to trade. Tune and backtest it before relying on it.
- Delta symbols vary by product and region. Check `/api/markets` and set `DELTA_SYMBOLS` to exact symbols returned by your account's regional public API. Defaults (`BTCUSD,ETHUSD`) are examples, not a guarantee that both are listed.
- This version monitors Delta public data only. Indian cash equities/currency derivatives and spot FX need a suitable licensed provider; they are not falsely presented as connected.
- REST polling is near-real-time rather than tick-level. Choose a poll interval that respects Delta rate limits. A candle may not be available immediately after its nominal close.
- SQLite is suitable for a single app process and modest use. Use managed PostgreSQL and a proper migration/queue strategy before scaling to multiple replicas.
- Keep the local device agent off in cloud deployment. The cloud dashboard does not automatically gain control over your laptop or iPhone.

## Quick local run

Requires a supported Python 3.11+ environment.

1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   # macOS/Linux: source .venv/bin/activate
   # Windows: .venv\\Scripts\\activate
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env`. Set `JARVIS_API_TOKEN` to a long random value. Set `DATABASE_PATH=jarvis.db` for local execution (the Docker example uses `/data/jarvis.db`).
3. Choose real symbols from Delta's product list and set `DELTA_SYMBOLS`, e.g. `BTCUSD,ETHUSD` only if listed.
4. Run `uvicorn app.main:app --host 127.0.0.1 --port 8000` and open `http://127.0.0.1:8000`.
5. Enter the API token in the dashboard. The API token is stored in session storage for that browser tab.

## Cloud deployment guide (Docker + HTTPS)

This is a single-server deployment for a small personal monitor. The cloud service remains online while the laptop is off. Use a supported, patched Linux VPS; do not deploy sensitive financial tooling on Windows 7.

### 1. Prepare a server and domain

- Create a small Ubuntu LTS/Debian VPS with Docker Engine and the Docker Compose plugin installed.
- Point a DNS `A` record for a domain/subdomain (for example `jarvis.example.com`) to the VPS public IPv4 address. Add an `AAAA` record only if the server's IPv6 connectivity is correctly configured.
- Allow inbound TCP 80 and 443 in the cloud firewall. Do not expose port 8000, SQLite, or a local-agent port to the internet.

### 2. Copy the project and set secrets

Upload/clone this project onto the server, then:

```bash
cp .env.example .env
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Paste the generated value into `JARVIS_API_TOKEN`. Set `JARVIS_DOMAIN=jarvis.example.com` in `.env` (replace with your domain), and make sure `DATABASE_PATH=/data/jarvis.db` remains set for the Docker volume. Set `DELTA_SYMBOLS` to symbols confirmed by `/api/markets`; set `DELTA_RESOLUTION` to one of `1m,3m,5m,15m,30m,1h,2h,4h,6h,1d,1w`. Keep `DELTA_READONLY_ENABLED=false` and leave Delta private credentials empty.

Do not commit `.env`, post it in chat, or bake it into an image. Restrict its filesystem permissions: `chmod 600 .env`.

### 3. Start HTTPS service

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f app caddy
```

Caddy reverse-proxies the app and requests/renews TLS certificates automatically when DNS and firewall settings are correct. The application container is not published directly to the host. Check `https://jarvis.example.com/health`, then open the same HTTPS domain and enter `JARVIS_API_TOKEN` in the dashboard.

To update later: back up the database, pull/copy the new code, run `docker compose up -d --build`, and verify `/health` and `/api/market/status`. The named `jarvis_data` volume persists the SQLite database across container rebuilds. Keep a separate encrypted backup; test restores.

### 4. Verify live data

- `GET /health` — public health check.
- `GET /api/markets` — authenticated Delta product list.
- `GET /api/market/status` — per-symbol poll status, last completed candle and estimated levels.
- `GET /api/market/candles?symbol=BTCUSD&resolution=5m&count=100` — recent completed candles for configured symbols.
- `GET /api/alerts` — generated alerts.

Authenticated endpoints require `Authorization: Bearer <JARVIS_API_TOKEN>`. Do not share this token. A `502` or per-symbol `error` indicates the public API is unreachable, the symbol/timeframe is invalid, or the upstream response changed; inspect server logs and the official API docs.

## iPhone push alerts via ntfy

1. Install the **ntfy** app from the iOS App Store: <https://ntfy.sh/>.
2. Create a long, unique topic name (use a random secret, not `jarvis` or a predictable name). Set it as `NTFY_TOPIC` in the server `.env`. Example generation: `python3 -c 'import secrets; print("jarvis-" + secrets.token_urlsafe(32))'`.
3. In the iPhone ntfy app, subscribe to the exact same topic and allow iOS notifications. Keep the topic private: on the public ntfy service, possession of the topic name is effectively access to its messages. For stronger privacy, use an authenticated ntfy account/server and set `NTFY_TOKEN`, or host a private ntfy instance with access controls.
4. Restart the app: `docker compose up -d`.
5. Verify by triggering a test alert in a non-production environment or temporarily using the manual signal endpoint. Check `docker compose logs app` if delivery fails.

The notification body includes symbol, timeframe, alert kind and level. If `NTFY_TOPIC` is empty, ntfy delivery is disabled. `ALERT_WEBHOOK_URL` is an optional additional destination; only use a trusted HTTPS endpoint.

## API reference

- `GET /health`
- `GET /api/markets`
- `GET /api/market/status`
- `GET /api/market/candles?symbol=BTCUSD&resolution=5m&count=100`
- `GET /api/alerts`
- `GET /api/news`
- `GET /api/delta/positions` — returns disabled/not implemented; this is intentional.
- `POST /api/signals/check` — manual/test input only.

## Security and financial safety

- Read-only public data only. There is no order placement, editing, or cancellation code.
- Private positions are intentionally disabled until the current Delta regional signing/authentication flow and endpoint are verified against official documentation and tested separately.
- Use a read-only API key only if private access is implemented in a future, separately reviewed change. Never grant trading permissions to this starter.
- Protect the dashboard with HTTPS and a long token. For multi-user/public production, add proper user accounts, rate limiting, audit logs, CSRF protections for browser-authenticated state changes, and managed secrets.
- Windows 7 is unsupported and unsafe for financial logins. Use an up-to-date OS and keep the cloud app independent of the old laptop.
