from flask import Flask, render_template, request, jsonify
from finance_api import get_stock_info

from openai import OpenAI

import os
import json


# ============================================================
# FLASK APPLICATION
# ============================================================

app = Flask(__name__)


# ============================================================
# OPENAI CLIENT
# ============================================================

# IMPORTANT:
# Set OPENAI_API_KEY as an environment variable.
#
# DO NOT put your API key directly inside this file.

client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY")
)


# ============================================================
# F11 AI SYSTEM INSTRUCTIONS
# ============================================================

SYSTEM_PROMPT = """
You are F11 AI, an intelligent financial and investment
analysis assistant.

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

You should communicate like a sophisticated venture-capital
and investment research analyst.

Your responses should be:

1. Clear
2. Analytical
3. Concise
4. Data-driven
5. Easy for a non-expert investor to understand

IMPORTANT:

When the user asks about a specific stock, ticker, company,
price, valuation or market data, use the F11 stock-data tool
instead of guessing.

Never invent financial numbers.

If current data is unavailable, clearly state that.

Do not claim that you executed a trade.

Do not independently place buy or sell orders.

For personalised investment advice, clearly distinguish
between financial information/analysis and regulated
investment advice.

When discussing a company, where data is available,
consider:

- Current price
- Price change
- Market capitalization
- P/E
- 52-week high
- Valuation
- Business quality
- Risk
- Growth
- Competitive position

Use a VC-style framework where appropriate:

BUSINESS
MARKET
GROWTH
UNIT ECONOMICS
VALUATION
RISKS
INVESTMENT VIEW

Do not fabricate missing information.
"""


# ============================================================
# TOOL DEFINITION
# ============================================================

tools = [

    {
        "type": "function",

        "name": "get_stock_info",

        "description": (
            "Retrieve stock information from the F11 "
            "Google Sheet and, if unavailable, live Yahoo "
            "Finance data. Use this whenever the user asks "
            "about a specific stock, ticker or company."
        ),

        "parameters": {

            "type": "object",

            "properties": {

                "query": {
                    "type": "string",
                    "description": (
                        "Stock ticker or company name. "
                        "Examples: AAPL, TSLA, RELIANCE"
                    )
                }

            },

            "required": ["query"]
        }
    }

]


# ============================================================
# TOOL EXECUTION
# ============================================================

def execute_tool(name, arguments):

    if name == "get_stock_info":

        query = arguments.get(
            "query",
            ""
        )

        result = get_stock_info(query)

        if result is None:

            return {
                "found": False,
                "query": query
            }

        return {
            "found": True,
            "data": result
        }

    return {
        "error": "Unknown tool"
    }


# ============================================================
# HOME PAGE
# ============================================================

@app.route("/")
def home():

    return render_template(
        "chat.html"
    )


# ============================================================
# CHAT API
# ============================================================

@app.route(
    "/chat",
    methods=["POST"]
)
def chat():

    try:

        data = request.get_json()

        user_message = (
            data.get("message", "")
            .strip()
        )

        if not user_message:

            return jsonify({
                "response":
                "Please enter a question."
            })


        # ====================================================
        # FIRST REQUEST TO GPT
        # ====================================================

        response = client.responses.create(

            model="gpt-5.6-luna",

            instructions=SYSTEM_PROMPT,

            tools=tools,

            input=user_message
        )


        # ====================================================
        # PROCESS TOOL CALLS
        # ====================================================

        while True:

            tool_calls = [
                item
                for item in response.output
                if item.type == "function_call"
            ]

            # ------------------------------------------------
            # No tool required
            # ------------------------------------------------

            if not tool_calls:

                break


            tool_outputs = []


            # ------------------------------------------------
            # Execute each requested tool
            # ------------------------------------------------

            for tool_call in tool_calls:

                try:

                    arguments = json.loads(
                        tool_call.arguments
                    )

                except Exception:

                    arguments = {}


                result = execute_tool(
                    tool_call.name,
                    arguments
                )


                tool_outputs.append({

                    "type":
                    "function_call_output",

                    "call_id":
                    tool_call.call_id,

                    "output":
                    json.dumps(result)

                })


            # ------------------------------------------------
            # Send tool results back to GPT
            # ------------------------------------------------

            response = client.responses.create(

                model="gpt-5.6-luna",

                instructions=SYSTEM_PROMPT,

                tools=tools,

                previous_response_id=
                response.id,

                input=tool_outputs
            )


        # ====================================================
        # FINAL AI RESPONSE
        # ====================================================

        answer = response.output_text


        return jsonify({

            "response": answer

        })


    except Exception as e:

        print(
            f"[F11 AI ERROR] {e}"
        )

        return jsonify({

            "response":
            "F11 AI is temporarily unable to process "
            "your request. Please try again."

        }), 500


# ============================================================
# RUN SERVER
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True,
        port=5000
    )
