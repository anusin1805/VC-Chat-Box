import os
import json
import logging
from datetime import datetime, timezone

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from google import genai
from google.genai import types

from finance_api import get_stock_info

# ---------------------------------------------------------
# APPLICATION & LOGGING
# ---------------------------------------------------------
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("f11-ai")

# ---------------------------------------------------------
# GEMINI CLIENT INITIALIZATION
# ---------------------------------------------------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# ---------------------------------------------------------
# SYSTEM PROMPT & TOOLS
# ---------------------------------------------------------
SYSTEM_PROMPT = """
You are F11 AI, the financial intelligence assistant inside the F11 investment application.

You help users understand Indian stocks, US stocks, stock prices, valuation, P/E ratios, and market risk.

IMPORTANT FINANCIAL DATA RULES:
1. NEVER invent a stock price, market cap, or P/E ratio.
2. When the user asks about a specific stock/ticker, ALWAYS use the get_stock_info tool.
3. If the tool cannot find the stock, state that F11 data source could not identify it.
4. Do not guarantee investment returns or present advice as certainty.
"""

tool_functions = {
    "get_stock_info": get_stock_info
}

# ---------------------------------------------------------
# HEALTH CHECK & FRONTEND
# ---------------------------------------------------------
@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "F11 AI",
        "model": "gemini-2.5-flash",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")

# ---------------------------------------------------------
# CHAT API ROUTE
# ---------------------------------------------------------
@app.route("/api/chat", methods=["POST", "OPTIONS"])
def chat():
    if request.method == "OPTIONS":
        return "", 204

    if not gemini_client:
        return jsonify({
            "success": False,
            "response": "Gemini API key is not configured on the server."
        }), 500

    try:
        payload = request.get_json(silent=True) or {}
        user_message = (
            payload.get("message")
            or payload.get("text")
            or payload.get("prompt")
            or payload.get("query")
            or ""
        ).strip()

        if not user_message:
            return jsonify({
                "success": False,
                "response": "Please enter a valid question."
            }), 400

        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[get_stock_info],
            temperature=0.1
        )

        # Initial call to Gemini
        response = gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=user_message,
            config=config
        )

        # Handle Function Calling Loop
        if response.function_calls:
            messages = [
                types.Content(role="user", parts=[types.Part.from_text(text=user_message)]),
                response.candidates[0].content
            ]

            for call in response.function_calls:
                fn_name = call.name
                fn_args = dict(call.args) if call.args else {}

                if fn_name in tool_functions:
                    try:
                        tool_result = tool_functions[fn_name](**fn_args)
                    except Exception as fn_err:
                        logger.error(f"Error executing function {fn_name}: {fn_err}")
                        tool_result = {"error": f"Failed to retrieve stock data: {str(fn_err)}"}

                    messages.append(
                        types.Content(
                            role="user",
                            parts=[
                                types.Part.from_function_response(
                                    name=fn_name,
                                    response={"result": tool_result}
                                )
                            ]
                        )
                    )

            # Re-query Gemini with tool outputs
            response = gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=messages,
                config=config
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
            "error": str(exc) if app.debug else None
        }), 500

# ---------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
