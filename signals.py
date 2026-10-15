from dataclasses import dataclass, asdict
from datetime import datetime, timezone

@dataclass
class Signal:
    symbol: str
    kind: str
    price: float
    level: float
    timeframe: str
    message: str
    candle_time: int | None = None


def check_candle(symbol, live_price, candle_close, support, resistance,
                 approach_pct=0.003, timeframe="15m"):
    """Compatibility helper for manual test inputs; production uses analyze_candles()."""
    out = []
    if support > 0 and abs(live_price-support)/support <= approach_pct:
        out.append(Signal(symbol, "support_approach", live_price, support, timeframe,
                          f"{symbol}: approaching support {support:g}; price {live_price:g}"))
    if resistance > 0 and abs(live_price-resistance)/resistance <= approach_pct:
        out.append(Signal(symbol, "resistance_approach", live_price, resistance, timeframe,
                          f"{symbol}: approaching resistance {resistance:g}; price {live_price:g}"))
    if resistance > 0 and candle_close > resistance:
        out.append(Signal(symbol, "breakout_confirmed", candle_close, resistance, timeframe,
                          f"{symbol}: completed candle closed above resistance {resistance:g}"))
    if support > 0 and candle_close < support:
        out.append(Signal(symbol, "breakdown_confirmed", candle_close, support, timeframe,
                          f"{symbol}: completed candle closed below support {support:g}"))
    return [asdict(s) for s in out]


def _pivot_levels(candles, window):
    highs, lows = [], []
    # Pivot only candles with enough bars on both sides. The right-side bars make
    # the level retrospective rather than pretending a not-yet-confirmed pivot is known.
    for i in range(window, len(candles) - window):
        c = candles[i]
        neighbours = candles[i-window:i] + candles[i+1:i+window+1]
        if all(c["high"] >= n["high"] for n in neighbours):
            highs.append(float(c["high"]))
        if all(c["low"] <= n["low"] for n in neighbours):
            lows.append(float(c["low"]))
    return highs, lows


def _nearest_level(levels, price):
    return min(levels, key=lambda x: abs(x-price)) if levels else None


def analyze_candles(symbol, candles, timeframe, approach_pct=0.003, pivot_window=3):
    """Use completed candles only. Returns alerts and a compact latest-candle summary."""
    if len(candles) < max(2 * pivot_window + 5, 15):
        return {"symbol": symbol, "timeframe": timeframe, "status": "insufficient_history",
                "candles": len(candles), "signals": []}
    # Candle timestamps and closes come from Delta's public OHLC endpoint. Caller has
    # already removed the currently forming candle.
    previous, latest = candles[-2], candles[-1]
    history = candles[:-1]
    highs, lows = _pivot_levels(history, pivot_window)
    if not highs or not lows:
        return {"symbol": symbol, "timeframe": timeframe, "status": "no_confirmed_pivots",
                "latest_candle_time": latest["time"], "close": latest["close"], "signals": []}
    support = _nearest_level(lows, previous["close"])
    resistance = _nearest_level(highs, previous["close"])
    close, prev_close = latest["close"], previous["close"]
    out = []
    if support and abs(close-support)/support <= approach_pct:
        out.append(Signal(symbol, "support_approach", close, support, timeframe,
                          f"{symbol} {timeframe}: completed close {close:g} is near support {support:g}", latest["time"]))
    if resistance and abs(close-resistance)/resistance <= approach_pct:
        out.append(Signal(symbol, "resistance_approach", close, resistance, timeframe,
                          f"{symbol} {timeframe}: completed close {close:g} is near resistance {resistance:g}", latest["time"]))
    # Crossing confirmation requires the previous completed close to be on/inside the
    # level and the latest completed close to finish beyond it. Intrabar wicks do not count.
    if resistance and prev_close <= resistance and close > resistance:
        out.append(Signal(symbol, "breakout_confirmed", close, resistance, timeframe,
                          f"{symbol} {timeframe}: candle closed above resistance {resistance:g}", latest["time"]))
    if support and prev_close >= support and close < support:
        out.append(Signal(symbol, "breakdown_confirmed", close, support, timeframe,
                          f"{symbol} {timeframe}: candle closed below support {support:g}", latest["time"]))
    return {"symbol": symbol, "timeframe": timeframe, "status": "ok",
            "latest_candle_time": latest["time"], "close": close,
            "support": support, "resistance": resistance,
            "signals": [asdict(s) for s in out]}


def dedupe_key(signal, cooldown_minutes=60):
    level = round(float(signal["level"]), 8)
    kind = signal["kind"]
    # Approach notifications are grouped into cooldown buckets; breakout/breakdown
    # notifications are keyed to the completed candle to avoid repeat polling alerts.
    if kind in {"support_approach", "resistance_approach"}:
        candle_time = int(signal.get("candle_time") or datetime.now(timezone.utc).timestamp())
        bucket = candle_time // (max(5, cooldown_minutes) * 60)
    else:
        bucket = int(signal.get("candle_time") or 0)
    return f"{signal['symbol']}|{signal['timeframe']}|{kind}|{level}|{bucket}"
