from flask import Flask, render_template, request, jsonify
from finance_api import get_stock_info
from openai import OpenAI
import os
import json

app = Flask(__name__)

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
Do not claim that you executed a trade or independently place orders.
"""

# Fixed OpenAI Tools Schema (Wrapped inside "function")
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

@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        user_message = data.get("message", "").strip()

        if not user_message:
            return jsonify({"response": "Please enter a question."})

        # Build initial message thread
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]

        # Call OpenAI Chat Completions
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )

        response_message = response.choices[0].message

        # Handle tool call requests
        if response_message.tool_calls:
            messages.append(response_message)  # Append assistant request to thread

            for tool_call in response_message.tool_calls:
                try:
                    arguments = json.loads(tool_call.function.arguments)
                except Exception:
                    arguments = {}

                tool_result = execute_tool(tool_call.function.name, arguments)

                # Append tool result message
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_result)
                })

            # Send complete thread back to model for final answer
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
    app.run(debug=True, port=5000)
