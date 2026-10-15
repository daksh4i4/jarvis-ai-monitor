import httpx
from .config import ALERT_WEBHOOK_URL, NTFY_BASE_URL, NTFY_TOPIC, NTFY_TOKEN

async def notify(alert):
    """Send to configured ntfy iPhone push and/or generic HTTPS webhook."""
    sent = False
    title = f"JARVIS {alert.get('kind', 'market alert')} — {alert.get('symbol', '')}"[:120]
    message = str(alert.get("message", "Market alert"))[:1500]
    async with httpx.AsyncClient(timeout=12, follow_redirects=False) as client:
        if NTFY_TOPIC:
            headers = {"Title": title, "Priority": "high" if "confirmed" in str(alert.get("kind", "")) else "default",
                       "Tags": "chart_with_upwards_trend"}
            if NTFY_TOKEN:
                headers["Authorization"] = f"Bearer {NTFY_TOKEN}"
            response = await client.post(f"{NTFY_BASE_URL}/{NTFY_TOPIC}", content=message.encode("utf-8"), headers=headers)
            response.raise_for_status()
            sent = True
        if ALERT_WEBHOOK_URL:
            response = await client.post(ALERT_WEBHOOK_URL, json=alert)
            response.raise_for_status()
            sent = True
    return sent
