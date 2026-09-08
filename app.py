import os
import logging
from datetime import datetime, timezone

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from google import genai
from google.genai import types

# Safe import to prevent startup crashes if finance_api has issues
try:
    from finance_api import get_stock_info
except Exception as e:
    get_stock_info = None

app = Flask(__name__, template_folder='.')
CORS(app, resources={r"/*": {"origins": "*"}})

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("f11-ai")

# 1. FIXED: Removed trailing comma & added 200 status code
@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok", 
        "service": "F11 AI",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }), 200

@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")

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

def safe_get_stock_info(ticker: str) -> str:
    """Fetch price and metric information for a given stock ticker symbol.
    
    Args:
        ticker: Ticker symbol or company name (e.g., 'RELIANCE', 'SEIL', 'AAPL').
    """
    if not get_stock_info:
        return "Stock data module is currently unavailable."
    
    try:
        symbol = str(ticker).strip().upper()
        result = get_stock_info(symbol)
        
        # Fallback to Indian stock suffixes if initial query returns no data
        if not result or "Could not find stock data" in str(result):
            if not symbol.endswith(('.NS', '.BO')):
                result = get_stock_info(f"{symbol}.NS")

        # Convert to plain text string to prevent SDK serialization crashes
        clean_text = str(result).replace("<b>", "").replace("</b>", "").replace("<br>", "\n")
        return clean_text

    except Exception as e:
        logger.error(f"Error executing stock lookup for {ticker}: {e}")
        return f"Unable to fetch data for ticker '{ticker}'."

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

        response = gemini_client.models.generate_content(
            model='gemini-3.6-flash',
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
