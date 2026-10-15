from app.signals import check_candle

def test_breakout():
    signals = check_candle("BTCUSDT", 101, 101, 90, 100, 0.003, "15m")
    assert any(s["kind"] == "breakout_confirmed" for s in signals)

def test_breakdown():
    signals = check_candle("BTCUSDT", 89, 89, 90, 100, 0.003, "15m")
    assert any(s["kind"] == "breakdown_confirmed" for s in signals)
from app.signals import analyze_candles, dedupe_key


def sample_candles(closes, highs=None, lows=None, step=300):
    rows = []
    for i, close in enumerate(closes):
        rows.append({"time": 1_700_000_000 + i * step,
                     "open": close, "high": highs[i] if highs else close + 1,
                     "low": lows[i] if lows else close - 1,
                     "close": close, "volume": 10})
    return rows


def test_dedupe_key_breakouts_is_per_candle():
    base = {"symbol": "BTCUSD", "timeframe": "5m", "kind": "breakout_confirmed",
            "level": 100, "candle_time": 1700000000}
    assert dedupe_key(base) == dedupe_key(base)
    assert dedupe_key(base) != dedupe_key({**base, "candle_time": 1700000300})


def test_dedupe_key_approach_is_bucketed():
    a = {"symbol": "BTCUSD", "timeframe": "5m", "kind": "support_approach",
         "level": 100, "candle_time": 1700000000}
    assert dedupe_key(a, 60) == dedupe_key({**a, "candle_time": 1700000100}, 60)


def test_analyzer_requires_enough_completed_candles():
    result = analyze_candles("BTCUSD", sample_candles(list(range(10, 20))), "5m")
    assert result["status"] == "insufficient_history"


def test_analyzer_returns_summary_with_completed_candles():
    # Oscillating prices produce confirmed local highs/lows.
    values = [100, 103, 101, 98, 96, 99, 102, 105, 101, 97, 95, 98,
              103, 106, 102, 99, 94, 97, 101, 104, 100, 96, 93, 97,
              102, 107, 103, 98, 92, 96, 101, 105, 100, 95, 91, 96]
    result = analyze_candles("BTCUSD", sample_candles(values), "5m", pivot_window=2)
    assert result["status"] == "ok"
    assert result["support"] is not None
    assert result["resistance"] is not None
    assert result["latest_candle_time"] == 1_700_000_000 + (len(values)-1)*300
