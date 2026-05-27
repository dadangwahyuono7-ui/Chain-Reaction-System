import urllib.request, urllib.parse, json
from datetime import datetime

def send(token, chat_id, text):
    if token == "YOUR_BOT_TOKEN":
        print(f"[TELEGRAM] {text}")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=5)

def now_wib():
    return datetime.now().strftime("%d/%m/%Y %H:%M WIB")

def msg_signal(signal_type, direction, price, sl, tp, chain):
    emoji = {"PYRAMID": "🏆", "NINJA": "🥷", "MICRO": "💎"}.get(signal_type, "⚡")
    dir_icon = "🟢 BUY" if direction == "BUY" else "🔴 SELL"
    return (
        f"{emoji} <b>{signal_type} {direction}</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"{dir_icon}\n"
        f"📍 Entry : <b>{price:.2f}</b>\n"
        f"🛑 SL    : <b>{sl:.2f}</b>\n"
        f"🎯 TP    : <b>{tp:.2f}</b>\n"
        f"⛓ Chain : {chain}\n"
        f"⏰ {now_wib()}\n"
        f"━━━━━━━━━━━━━━\n"
        f"<i>SOP AKAR v3.0 — Chain Reaction</i>"
    )

def msg_exit(direction, price, reason):
    return (
        f"❌ <b>EXIT SIGNAL</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"Posisi : {direction}\n"
        f"Harga  : <b>{price:.2f}</b>\n"
        f"Alasan : {reason}\n"
        f"⏰ {now_wib()}"
    )

def msg_status(state_str, price):
    return (
        f"📊 <b>STATUS ENGINE</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"{state_str}\n"
        f"Price: {price:.2f}\n"
        f"⏰ {now_wib()}"
    )
