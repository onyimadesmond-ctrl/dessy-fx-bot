import os
import yfinance as yf
import pandas as pd
import requests
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

BOT_TOKEN = "8722830088:AAFJ3TTivYvBxr7UNWDUyfwxLBNdA4KDhtA"
PAIRS = {"USDCHF=X": "USD/CHF", "CHFJPY=X": "CHF/JPY"}

# ─── TELEGRAM HELPERS ─────────────────────────────────
def send(chat_id, msg, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": msg,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json=payload,
        timeout=10
    )

def edit(chat_id, message_id, msg, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": msg,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText",
        json=payload,
        timeout=10
    )

def answer_callback(callback_id):
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery",
        json={"callback_query_id": callback_id},
        timeout=10
    )

def get_signal_button():
    return {
        "inline_keyboard": [[
            {"text": "Get Signal 📊", "callback_data": "get_signal"}
        ]]
    }

# ─── INDICATORS ───────────────────────────────────────
def heiken_ashi(df):
    ha = pd.DataFrame(index=df.index)
    ha['Close'] = (df['Open'] + df['High'] + df['Low'] + df['Close']) / 4
    ha_open = [(df['Open'].iloc[0] + df['Close'].iloc[0]) / 2]
    for i in range(1, len(df)):
        ha_open.append((ha_open[i-1] + ha['Close'].iloc[i-1]) / 2)
    ha['Open'] = ha_open
    ha['High'] = pd.concat([df['High'], ha['Open'], ha['Close']], axis=1).max(axis=1)
    ha['Low'] = pd.concat([df['Low'], ha['Open'], ha['Close']], axis=1).min(axis=1)
    return ha

def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def momentum(series, period):
    return series - series.shift(period)

def williams_r(df, period):
    hh = df['High'].rolling(period).max()
    ll = df['Low'].rolling(period).min()
    return -100 * (hh - df['Close']) / (hh - ll)

# ─── ANALYZE ──────────────────────────────────────────
def analyze():
    results = []

    for ticker, name in PAIRS.items():
        try:
            df = yf.download(ticker, period="2d", interval="1m", progress=False)
            if df.empty or len(df) < 210:
                results.append(f"⚠️ <b>{name}</b> — Not enough data")
                continue

            ha     = heiken_ashi(df)
            ema200 = ema(df['Close'], 200)
            mom    = momentum(df['Close'], 10)
            wr     = williams_r(df, 45)

            i = -1

            ha_above = float(ha['Close'].iloc[i]) > float(ema200.iloc[i])
            ha_below = float(ha['Close'].iloc[i]) < float(ema200.iloc[i])
            ha_bull  = float(ha['Close'].iloc[i]) > float(ha['Open'].iloc[i])
            ha_bear  = float(ha['Close'].iloc[i]) < float(ha['Open'].iloc[i])

            mom_bull = float(mom.iloc[i]) > 0 and float(mom.iloc[i]) > float(mom.iloc[i-1])
            mom_bear = float(mom.iloc[i]) < 0 and float(mom.iloc[i]) < float(mom.iloc[i-1])

            wr_up   = float(wr.iloc[i-1]) <= -20 and float(wr.iloc[i]) > -20
            wr_down = float(wr.iloc[i-1]) >= -80 and float(wr.iloc[i]) < -80

            now = datetime.now().strftime("%H:%M:%S")

            if ha_above and ha_bull and mom_bull and wr_up:
                results.append(
                    f"🟢 <b>BUY — {name}</b>\n"
                    f"⏱ Expiry: 30s  |  🕐 {now}\n"
                    f"━━━━━━━━━━━━━━━━\n"
                    f"✅ HA candle above 200 EMA\n"
                    f"✅ Momentum 10 bullish\n"
                    f"✅ Williams %R crossed -20\n"
                    f"━━━━━━━━━━━━━━━━\n"
                    f"⚡ <b>HIGH CONFIDENCE — ENTER NOW</b>"
                )
            elif ha_below and ha_bear and mom_bear and wr_down:
                results.append(
                    f"🔴 <b>SELL — {name}</b>\n"
                    f"⏱ Expiry: 30s  |  🕐 {now}\n"
                    f"━━━━━━━━━━━━━━━━\n"
                    f"✅ HA candle below 200 EMA\n"
                    f"✅ Momentum 10 bearish\n"
                    f"✅ Williams %R crossed -80\n"
                    f"━━━━━━━━━━━━━━━━\n"
                    f"⚡ <b>HIGH CONFIDENCE — ENTER NOW</b>"
                )
            else:
                bull_count = [ha_above and ha_bull, mom_bull, wr_up].count(True)
                bear_count = [ha_below and ha_bear, mom_bear, wr_down].count(True)
                closest = "bull" if bull_count >= bear_count else "bear"
                count = max(bull_count, bear_count)

                c1 = "✅" if (ha_above and ha_bull if closest == "bull" else ha_below and ha_bear) else "❌"
                c2 = "✅" if (mom_bull if closest == "bull" else mom_bear) else "❌"
                c3 = "✅" if (wr_up if closest == "bull" else wr_down) else "❌"

                results.append(
                    f"⏸ <b>NO SIGNAL — {name}</b>\n"
                    f"🕐 {now}  |  {count}/3 confirmations\n"
                    f"━━━━━━━━━━━━━━━━\n"
                    f"{c1} HA vs 200 EMA\n"
                    f"{c2} Momentum 10\n"
                    f"{c3} Williams %R\n"
                    f"━━━━━━━━━━━━━━━━\n"
                    f"⚠️ <b>Not ready. Wait for full confirmation.</b>"
                )

        except Exception as e:
            results.append(f"⚠️ <b>{name}</b> — Error: {str(e)}")

    return "\n\n".join(results)

# ─── WEBHOOK ──────────────────────────────────────────
@app.route(f"/webhook/{BOT_TOKEN}", methods=["POST"])
def webhook():
    data = request.json
    if not data:
        return jsonify({"ok": True})

    try:
        # Handle inline button tap
        if "callback_query" in data:
            cb      = data["callback_query"]
            chat_id = str(cb["message"]["chat"]["id"])
            msg_id  = cb["message"]["message_id"]
            action  = cb["data"]
            cb_id   = cb["id"]

            answer_callback(cb_id)

            if action == "get_signal":
                edit(chat_id, msg_id,
                    "🔍 <b>Analyzing market...</b>\nPlease wait ⏳",
                    None
                )
                result = analyze()
                send(chat_id, result, reply_markup=get_signal_button())

        # Handle text messages
        elif "message" in data:
            msg     = data["message"]
            chat_id = str(msg["chat"]["id"])
            text    = msg.get("text", "").strip().lower()

            if text == "/start":
                send(chat_id,
                    "👋 <b>Welcome to Dessy FX Bot</b>\n"
                    "━━━━━━━━━━━━━━━━\n"
                    "📊 Pairs: USD/CHF | CHF/JPY\n"
                    "📐 Strategy: D2 Modified\n"
                    "⏱ Expiry: 30 seconds\n"
                    "━━━━━━━━━━━━━━━━\n"
                    "Tap the button below to scan the market 👇",
                    reply_markup=get_signal_button()
                )

    except Exception as e:
        print(f"Webhook error: {e}")

    return jsonify({"ok": True})

@app.route("/")
def home():
    return "Dessy FX Bot is running."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
