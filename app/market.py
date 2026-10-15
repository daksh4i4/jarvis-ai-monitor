from datetime import datetime, timezone
import httpx
from .config import DELTA_BASE_URL

RESOLUTION_SECONDS = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "2h": 7200, "4h": 14400, "6h": 21600, "1d": 86400,
    "1w": 604800,
}

class DeltaPublicMarket:
    """Unauthenticated, read-only Delta public market-data client."""
    def __init__(self, base_url=DELTA_BASE_URL):
        self.base_url = base_url.rstrip("/")

    async def _get(self, path, params=None):
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
            response = await client.get(f"{self.base_url}{path}", params=params,
                                        headers={"Accept": "application/json", "User-Agent": "jarvis-market-monitor/1.0"})
            response.raise_for_status()
            data = response.json()
        if isinstance(data, dict) and data.get("success") is False:
            raise RuntimeError("Delta public API reported success=false")
        return data

    async def products(self):
        data = await self._get("/v2/products", {"page_size": 200})
        return data.get("result", [])

    async def candles(self, symbol, resolution="5m", count=150, now=None):
        if resolution not in RESOLUTION_SECONDS:
            raise ValueError(f"Unsupported candle resolution: {resolution}")
        count = min(2000, max(10, int(count)))
        now = int(now if now is not None else datetime.now(timezone.utc).timestamp())
        seconds = RESOLUTION_SECONDS[resolution]
        # Delta candle timestamps are UTC Unix seconds. Fetch one extra interval so the
        # most recent, still-forming candle can be excluded conservatively below.
        data = await self._get("/v2/history/candles", {
            "resolution": resolution, "symbol": symbol,
            "start": now - seconds * (count + 2), "end": now,
        })
        rows = data.get("result", [])
        if not isinstance(rows, list):
            raise RuntimeError("Unexpected Delta candle response shape")
        candles = []
        for row in rows:
            try:
                candle = {"time": int(row["time"]), "open": float(row["open"]),
                          "high": float(row["high"]), "low": float(row["low"]),
                          "close": float(row["close"]), "volume": float(row.get("volume", 0) or 0)}
                if candle["time"] + seconds <= now:
                    candles.append(candle)
            except (KeyError, TypeError, ValueError):
                continue
        candles.sort(key=lambda c: c["time"])
        # Keep unique timestamps and latest count completed candles.
        by_time = {c["time"]: c for c in candles}
        return [by_time[t] for t in sorted(by_time)[-count:]]

class IndianMarketAdapter:
    async def candles(self, symbol, timeframe):
        raise NotImplementedError("Configure a licensed Indian market-data provider.")

class ForexAdapter:
    async def candles(self, pair, timeframe):
        raise NotImplementedError("Configure a forex data provider and confirm license/coverage.")
