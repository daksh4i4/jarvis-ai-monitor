# Production checklist

- [ ] Use a supported, patched Linux host, HTTPS, a long random API token, firewall rules, and secret-file permissions.
- [ ] Confirm DNS and Caddy certificate issuance; do not expose port 8000 publicly.
- [ ] Confirm configured Delta symbols exist in the current regional public product response.
- [ ] Confirm candles are updating and only completed candles are analysed.
- [ ] Review the pivot-based levels and dedupe behavior against chart history before relying on alerts.
- [ ] Configure ntfy iOS notifications with a private/unpredictable topic; prefer an authenticated or self-hosted ntfy server for sensitive messages.
- [ ] Test alert delivery, notification permissions, app restarts, disk persistence, backups, and restores.
- [ ] Monitor upstream errors and rate limits; tune `MARKET_POLL_SECONDS` and symbol count conservatively.
- [ ] Use PostgreSQL and a durable queue/migration process before multi-replica deployment.
- [ ] Indian stocks, Indian currency derivatives and spot forex require a separate licensed data provider; they are not included.
- [ ] Keep `DELTA_READONLY_ENABLED=false`; private positions are not implemented until current regional auth/signing is verified.
- [ ] No order-placement endpoint is present. Do not add one as part of the monitoring deployment.
- [ ] Keep any local device agent off the cloud host and never expose it directly to the internet.
