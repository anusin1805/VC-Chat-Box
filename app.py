import os
import logging
from datetime import datetime, timezone

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from google import genai
from google.genai import types

from finance_api import get_stock_info

app = Flask(__name__, template_folder='.')
CORS(app, resources={r"/*": {"origins": "*"}})

@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "F11 AI"}),

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("f11-ai")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

SYSTEM_PROMPT = """
You are F11 AI, the financial intelligence assistant inside the F11 investment application.
You help users understand Indian stocks, US stocks, stock prices, valuation, P/E ratios, and market risk.

IMPORTANT FINANCIAL DATA RULES:
1. NEVER invent a stock price, market cap, or P/E ratio.
2. When the user asks about a specific stock/ticker, ALWAYS use the get_stock_info tool.
3. If the tool cannot find the stock, state that F11 data source could not identify it.
4. Do not guarantee investment returns or present advice as certainty.
"""

# 1. Wrap the function to prevent crashes during automatic execution
def safe_get_stock_info(ticker: str) -> dict:
    """Fetch current stock price, P/E ratio, and market cap for a given ticker.
    Args:
        ticker: The stock ticker symbol (e.g., 'AAPL', 'RELIANCE.NS').
    """
    try:
        result = get_stock_info(ticker)
        return result if result else {"error": f"No data found for {ticker}."}
    except Exception as e:
        logger.error(f"Error fetching stock data for {ticker}: {e}")
        return {"error": f"Could not retrieve data for {ticker}. The ticker may be invalid or unsupported."}


@app.route("/api/chat", methods=["POST", "OPTIONS"])
def chat():
    if request.method == "OPTIONS":
        return "", 204

    if not gemini_client:
        return jsonify({"success": False, "response": "Gemini API key missing."}), 500

    try:
        payload = request.get_json(silent=True) or {}
        user_message = (
            payload.get("message") or payload.get("text") or payload.get("prompt") or ""
        ).strip()

        if not user_message:
            return jsonify({"success": False, "response": "Please enter a valid question."}), 400

        # 2. The SDK automatically calls safe_get_stock_info when needed
        response = gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                tools=[safe_get_stock_info],
                temperature=0.1
            )
        )

        return jsonify({
            "success": True,
            "response": response.text,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    except Exception as exc:
        logger.exception("F11 AI request failed")
        return jsonify({
            "success": False,
            "response": "F11 AI is temporarily unavailable. Please try again.",
            "error": str(exc) if app.debug else "Internal Server Error"
        }), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
