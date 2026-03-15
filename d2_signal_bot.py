import os
import base64
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)

BOT_TOKEN = "8722830088:AAFJ3TTivYvBxr7UNWDUyfwxLBNdA4KDhtA"
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# ─── TELEGRAM HELPERS ─────────────────────────────────
def send(chat_id, msg, reply_markup=None):
    payload = {"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json=payload, timeout=10)

def edit(chat_id, message_id, msg, reply_markup=None):
    payload = {"chat_id": chat_id, "message_id": message_id, "text": msg, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText", json=payload, timeout=10)

def answer_callback(callback_id):
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery",
                  json={"callback_query_id": callback_id}, timeout=10)

def get_signal_button():
    return {"inline_keyboard": [[{"text": "Get Signal 📊", "callback_data": "get_signal"}]]}

# ─── IMAGE ANALYSIS ENDPOINT ──────────────────────────
@app.route("/analyze", methods=["POST", "OPTIONS"])
def analyze():
    if request.method == "OPTIONS":
        return jsonify({"ok": True})

    try:
        data = request.json
        image_base64 = data.get("image")
        media_type = data.get("media_type", "image/jpeg")

        if not image_base64:
            return jsonify({"error": "No image provided"}), 400

        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01"
            },
            json={
                "model": "claude-opus-4-5-20251101",
                "max_tokens": 500,
                "system": """You are Dessy FX Bot — an expert binary options chart analyst.

The trader uses Pocket Option with Heiken Ashi candles on 5-minute timeframe, 5-minute expiry.
They enter at the OPEN of the NEXT candle after your signal.

Analyze the chart screenshot and give BUY or SELL. Always give one — never refuse or say no signal.

Look at:
- Overall trend direction
- Last 3-5 candle colors and momentum
- Any clear support/resistance levels
- Heiken Ashi body size and color sequence
- Whether price is in a trend or reversal

Be decisive like a professional trader. Be honest about confidence.

Respond ONLY with valid JSON, no markdown, no extra text:
{"signal":"BUY","confidence":78,"reason":"2-3 sentence analysis of what you see and why you're calling this direction"}""",
                "messages": [{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_base64
                            }
                        },
                        {
                            "type": "text",
                            "text": "Analyze this Heiken Ashi chart. Give BUY or SELL for the next 5-minute candle."
                        }
                    ]
                }]
            },
            timeout=30
        )

        result = response.json()

        if "error" in result:
            return jsonify({"error": result["error"].get("message", "API error")}), 500

        text = result["content"][0]["text"].replace("```json", "").replace("```", "").strip()
        import json
        signal_data = json.loads(text)
        return jsonify(signal_data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── TELEGRAM WEBHOOK ─────────────────────────────────
@app.route(f"/webhook/{BOT_TOKEN}", methods=["POST"])
def webhook():
    data = request.json
    if not data:
        return jsonify({"ok": True})

    try:
        if "callback_query" in data:
            cb = data["callback_query"]
            chat_id = str(cb["message"]["chat"]["id"])
            msg_id = cb["message"]["message_id"]
            action = cb["data"]
            cb_id = cb["id"]

            answer_callback(cb_id)

            if action == "get_signal":
                edit(chat_id, msg_id, "🔍 <b>Analyzing market...</b>\nPlease wait ⏳", None)
                send(chat_id,
                     "📸 <b>Screenshot bot is now active!</b>\n"
                     "━━━━━━━━━━━━━━━━\n"
                     "Open the web bot, upload your Heiken Ashi chart screenshot and get your signal.\n"
                     "━━━━━━━━━━━━━━━━\n"
                     "Settings: Heiken Ashi • 5 Min TF • 5 Min Expiry",
                     reply_markup=get_signal_button())

        elif "message" in data:
            msg = data["message"]
            chat_id = str(msg["chat"]["id"])
            text = msg.get("text", "").strip().lower()

            if text == "/start":
                send(chat_id,
                     "👋 <b>Welcome to Dessy FX Bot</b>\n"
                     "━━━━━━━━━━━━━━━━\n"
                     "📊 Strategy: Screenshot Analysis\n"
                     "📐 Chart: Heiken Ashi\n"
                     "⏱ Timeframe: 5 Minutes\n"
                     "🎯 Expiry: 5 Minutes\n"
                     "━━━━━━━━━━━━━━━━\n"
                     "Tap below to get started 👇",
                     reply_markup=get_signal_button())

    except Exception as e:
        print(f"Webhook error: {e}")

    return jsonify({"ok": True})


@app.route("/")
def home():
    return "Dessy FX Bot is running."


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
        
