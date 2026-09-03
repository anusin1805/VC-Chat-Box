from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from finance_api import get_stock_info
from openai import OpenAI
import os
import json

app = Flask(__name__)

# ENABLE CORS FOR ALL ORIGINS (Allows requests from GitHub Pages)
CORS(app, resources={r"/*": {"origins": "*"}})

# Initialize OpenAI Client
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
You are F11 AI, an intelligent financial and investment analysis assistant.
You are part of the F11 financial application.

Your job is to help users understand:
- Stocks
- Market prices
- Company fundamentals
- Portfolio information
- Investment concepts
- Market trends
- Risk
- Valuation
- Financial metrics

You should communicate like a sophisticated venture-capital and investment research analyst.

Your responses should be:
1. Clear
2. Analytical
3. Concise
4. Data-driven
5. Easy for a non-expert investor to understand

IMPORTANT:
When the user asks about a specific stock, ticker, company, price, valuation or market data, use the F11 stock-data tool instead of guessing.
Never invent financial numbers.
If current data is unavailable, clearly state that.
"""

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_stock_info",
            "description": (
                "Retrieve stock information from the F11 Google Sheet and live Yahoo Finance data. "
                "Use this whenever the user asks about a specific stock, ticker or company."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Stock ticker or company name. Examples: AAPL, TSLA, RELIANCE"
                    }
                },
                "required": ["query"]
            }
        }
    }
]

def execute_tool(name, arguments):
    if name == "get_stock_info":
        query = arguments.get("query", "")
        result = get_stock_info(query)
        if result is None:
            return {"found": False, "query": query}
        return {"found": True, "data": result}
    return {"error": "Unknown tool"}

@app.route("/")
def home():
    return render_template("chat.html")

@app.route("/chat", methods=["POST", "OPTIONS"])
def chat():
    # Handle CORS Preflight OPTIONS requests
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    try:
        data = request.get_json(silent=True) or {}
        
        # Safely capture message from varying JSON payload structures
        user_message = (
            data.get("message") or 
            data.get("text") or 
            data.get("prompt") or 
            data.get("query") or 
            ""
        ).strip()

        if not user_message:
            return jsonify({"response": "Please enter a valid stock query."})

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )

        response_message = response.choices[0].message

        if response_message.tool_calls:
            messages.append(response_message)

            for tool_call in response_message.tool_calls:
                try:
                    arguments = json.loads(tool_call.function.arguments)
                except Exception:
                    arguments = {}

                tool_result = execute_tool(tool_call.function.name, arguments)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_result)
                })

            second_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages
            )
            answer = second_response.choices[0].message.content
        else:
            answer = response_message.content

        return jsonify({"response": answer})

    except Exception as e:
        print(f"[F11 AI ERROR] {e}")
        return jsonify({
            "response": "F11 AI is temporarily unable to process your request. Please try again."
        }), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

