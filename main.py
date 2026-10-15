import asyncio
from datetime import datetime, timezone
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from .config import (APP_NAME, POLL_SECONDS, MARKET_POLL_SECONDS, LOCAL_AGENT_URL, LOCAL_AGENT_TOKEN,
                     DELTA_SYMBOLS, DELTA_RESOLUTION, DELTA_LOOKBACK_CANDLES, SR_PIVOT_WINDOW,
                     SR_APPROACH_PCT, ALERT_COOLDOWN_MINUTES)
from .db import init_db, save_alert, get_alerts, save_news, get_news
from .market import DeltaPublicMarket
from .signals import check_candle, analyze_candles, dedupe_key
from .market import RESOLUTION_SECONDS
from .news import fetch_news
from .notifier import notify
from .security import require_token
from .delta_private import DeltaReadOnlyAccount

market = DeltaPublicMarket()
market_status = {"configured_symbols": DELTA_SYMBOLS, "resolution": DELTA_RESOLUTION,
                 "last_poll_at": None, "symbols": {}, "mode": "public_read_only"}

async def news_polling_loop():
    while True:
        try:
            save_news(await fetch_news())
        except Exception as exc:
            # Keep the service alive; operational details are exposed in server logs only.
            print(f"news polling failed: {type(exc).__name__}")
        await asyncio.sleep(max(POLL_SECONDS, 60))

async def market_polling_loop():
    while True:
        market_status["last_poll_at"] = datetime.now(timezone.utc).isoformat()
        for symbol in DELTA_SYMBOLS:
            try:
                candles = await market.candles(symbol, DELTA_RESOLUTION, DELTA_LOOKBACK_CANDLES)
                analysis = analyze_candles(symbol, candles, DELTA_RESOLUTION,
                                           SR_APPROACH_PCT, SR_PIVOT_WINDOW)
                market_status["symbols"][symbol] = {
                    "status": analysis.get("status", "ok"),
                    "last_candle_time": analysis.get("latest_candle_time"),
                    "close": analysis.get("close"), "support": analysis.get("support"),
                    "resistance": analysis.get("resistance"), "candles": len(candles), "error": None}
                for signal in analysis.get("signals", []):
                    key = dedupe_key(signal, ALERT_COOLDOWN_MINUTES)
                    _, created = save_alert(signal["symbol"], signal["kind"], signal["message"], signal, key)
                    if created:
                        try:
                            await notify(signal)
                        except Exception as exc:
                            print(f"notification delivery failed: {type(exc).__name__}")
            except Exception as exc:
                market_status["symbols"][symbol] = {"status": "error", "error": type(exc).__name__}
        await asyncio.sleep(MARKET_POLL_SECONDS)

@asynccontextmanager
async def lifespan(app):
    init_db()
    tasks = [asyncio.create_task(news_polling_loop()), asyncio.create_task(market_polling_loop())]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

app = FastAPI(title=APP_NAME, lifespan=lifespan)

@app.get("/", response_class=HTMLResponse)
async def home():
    return HTMLResponse(DASHBOARD)

@app.get("/health")
async def health():
    return {"ok": True, "news_polling": "enabled", "market_candle_polling": "enabled", "mode": "public_read_only"}

@app.get("/api/markets", dependencies=[Depends(require_token)])
async def markets():
    try:
        return {"source": "Delta public products", "products": (await market.products())[:200]}
    except Exception as e:
        raise HTTPException(502, f"Delta public API unavailable: {type(e).__name__}")

@app.get("/api/market/status", dependencies=[Depends(require_token)])
async def market_monitor_status():
    return market_status

@app.get("/api/market/candles", dependencies=[Depends(require_token)])
async def market_candles(symbol: str, resolution: str | None = None, count: int = 100):
    symbol = symbol.upper().strip()
    resolution = resolution or DELTA_RESOLUTION
    if symbol not in DELTA_SYMBOLS:
        raise HTTPException(400, "Symbol must be included in DELTA_SYMBOLS in the server environment.")
    if resolution not in RESOLUTION_SECONDS:
        raise HTTPException(400, f"Unsupported resolution. Choose: {', '.join(RESOLUTION_SECONDS)}")
    if count < 10 or count > 500:
        raise HTTPException(400, "count must be between 10 and 500")
    try:
        rows = await market.candles(symbol, resolution, count)
        return {"symbol": symbol, "resolution": resolution, "count": len(rows), "candles": rows}
    except Exception as exc:
        raise HTTPException(502, f"Delta candle API unavailable: {type(exc).__name__}")

@app.get("/api/alerts", dependencies=[Depends(require_token)])
async def alerts():
    return get_alerts()

@app.get("/api/news", dependencies=[Depends(require_token)])
async def news():
    return get_news()

@app.get("/api/delta/positions", dependencies=[Depends(require_token)])
async def positions():
    try:
        return await DeltaReadOnlyAccount().positions()
    except NotImplementedError as e:
        raise HTTPException(501, str(e))
    except RuntimeError as e:
        raise HTTPException(403, str(e))

class SignalRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=40)
    live_price: float = Field(gt=0)
    completed_candle_close: float = Field(gt=0)
    support: float = Field(gt=0)
    resistance: float = Field(gt=0)
    approach_pct: float = Field(default=0.003, ge=0.0001, le=0.05)
    timeframe: str = Field(default="15m", max_length=12)

@app.post("/api/signals/check", dependencies=[Depends(require_token)])
async def signal_check(body: SignalRequest):
    signals = check_candle(body.symbol, body.live_price, body.completed_candle_close,
                           body.support, body.resistance, body.approach_pct, body.timeframe)
    for s in signals:
        _, created = save_alert(s["symbol"], s["kind"], s["message"], s)
        if created:
            try:
                await notify(s)
            except Exception:
                pass
    return {"signals": signals, "warning": "Manual/test values; not a live signal feed."}

class DeviceCommand(BaseModel):
    action: str
    target: str

@app.post("/api/device/command", dependencies=[Depends(require_token)])
async def device_command(body: DeviceCommand):
    if body.action not in {"open_url", "open_app"}:
        raise HTTPException(400, "Action not allowlisted.")
    if not LOCAL_AGENT_URL or not LOCAL_AGENT_TOKEN:
        raise HTTPException(503, "Configure local agent URL and token.")
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.post(LOCAL_AGENT_URL + "/command",
                headers={"Authorization": f"Bearer {LOCAL_AGENT_TOKEN}"},
                json=body.model_dump())
            r.raise_for_status()
            return r.json()
    except Exception as e:
        raise HTTPException(502, f"Local agent unavailable: {type(e).__name__}")

DASHBOARD = r'''<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>JARVIS AI</title>
<style>
body{font-family:Arial,sans-serif;background:#0b1020;color:#e8edf8;margin:0;padding:20px}
main{max-width:1100px;margin:auto}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}
.card{background:#151d31;border:1px solid #2b3854;border-radius:14px;padding:16px;margin:10px 0}
input,button{background:#0d1426;color:#e8edf8;border:1px solid #384766;border-radius:8px;padding:10px;margin:4px;max-width:95%}
button{cursor:pointer;background:#294a7d}a{color:#8fc8ff}small,.muted{color:#9daac4}li{margin:8px 0;overflow-wrap:anywhere}
</style></head><body><main><h1>JARVIS AI</h1><p class="muted">Read-only financial intelligence and device-control starter</p>
<div class="card">API token <input id="token" type="password" autocomplete="off"><button onclick="saveToken()">Use token</button><span id="status"></span></div>
<div class="grid">
<div class="card"><h2>Voice / commands</h2><button onclick="listen()">🎙 Listen</button><button onclick="speak('JARVIS dashboard ready')">🔊 Speak</button>
<p id="heard"></p><input id="command" placeholder="open Delta / open TradingView"><button onclick="command()">Run command</button>
<p class="muted">Speech support varies by browser. Local agent must be running for device actions.</p></div>
<div class="card"><h2>Signal test</h2>
<input id="symbol" value="BTCUSDT"><input id="price" type="number" value="67900" placeholder="Live price">
<input id="close" type="number" value="68100" placeholder="Completed candle close">
<input id="support" type="number" value="60000" placeholder="Support"><input id="resistance" type="number" value="68000" placeholder="Resistance">
<button onclick="signal()">Check test signal</button><pre id="result"></pre></div>
<div class="card"><h2>Alerts</h2><button onclick="alerts()">Refresh</button><ul id="alertList"></ul></div>
<div class="card"><h2>News</h2><button onclick="news()">Refresh</button><ul id="newsList"></ul></div>
<div class="card"><h2>Live Delta monitor</h2><button onclick="marketStatus()">Refresh status</button><pre id="monitorStatus"></pre><p class="muted">Completed candles only; support/resistance pivots are heuristic, not guaranteed levels.</p></div><div class="card"><h2>Delta products</h2><button onclick="markets()">Load</button><pre id="marketList"></pre></div>
</div><p class="muted">No order placement. Do not use Windows 7 for sensitive financial logins.</p></main>
<script>
let tok=sessionStorage.getItem('jarvis_token')||'';document.getElementById('token').value=tok;
function saveToken(){tok=document.getElementById('token').value;sessionStorage.setItem('jarvis_token',tok);document.getElementById('status').textContent=' token saved in this tab'}
async function api(p,o={}){let r=await fetch(p,{...o,headers:{'Content-Type':'application/json','Authorization':'Bearer '+tok,...(o.headers||{})}});let d=await r.json();if(!r.ok)throw Error(d.detail||r.statusText);return d}
function esc(s){return String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
async function alerts(){try{let a=await api('/api/alerts');document.getElementById('alertList').innerHTML=a.map(x=>`<li><b>${esc(x.kind)}</b> ${esc(x.symbol)} — ${esc(x.message)}</li>`).join('')||'<li>No alerts yet</li>'}catch(e){alert(e.message)}}
async function news(){try{let a=await api('/api/news');document.getElementById('newsList').innerHTML=a.map(x=>`<li><a target="_blank" rel="noopener" href="${esc(x.link)}">${esc(x.title)}</a><br><small>${esc(x.source)}</small></li>`).join('')||'<li>No news yet</li>'}catch(e){alert(e.message)}}
async function markets(){try{let a=await api('/api/markets');document.getElementById('marketList').textContent=JSON.stringify(a.products.slice(0,30).map(p=>({symbol:p.symbol,id:p.id})),null,2)}catch(e){alert(e.message)}}
async function marketStatus(){try{let a=await api('/api/market/status');document.getElementById('monitorStatus').textContent=JSON.stringify(a,null,2)}catch(e){alert(e.message)}}
async function signal(){try{let a=await api('/api/signals/check',{method:'POST',body:JSON.stringify({symbol:document.getElementById('symbol').value,live_price:+document.getElementById('price').value,completed_candle_close:+document.getElementById('close').value,support:+document.getElementById('support').value,resistance:+document.getElementById('resistance').value})});document.getElementById('result').textContent=JSON.stringify(a,null,2);alerts()}catch(e){alert(e.message)}}
function speak(t){if('speechSynthesis'in window)speechSynthesis.speak(new SpeechSynthesisUtterance(t));else alert(t)}
function listen(){let S=window.SpeechRecognition||window.webkitSpeechRecognition;if(!S)return alert('Speech recognition unavailable; use text commands.');let r=new S();r.lang='en-IN';r.onresult=e=>{let t=e.results[0][0].transcript;document.getElementById('heard').textContent=t;document.getElementById('command').value=t};r.start()}
async function command(){let c=document.getElementById('command').value.toLowerCase();let target=c.includes('delta')?'https://www.delta.exchange/':c.includes('tradingview')?'https://www.tradingview.com/':'';if(!target)return alert('Allowed commands: open Delta, open TradingView');try{let r=await api('/api/device/command',{method:'POST',body:JSON.stringify({action:'open_url',target})});speak(r.message||'Command sent')}catch(e){alert(e.message)}}
</script></body></html>'''
