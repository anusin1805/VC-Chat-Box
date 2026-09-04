import os
import json
import logging
from datetime import datetime, timezone

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from openai import OpenAI

from finance_api import get_stock_info


# ---------------------------------------------------------
# APPLICATION
# ---------------------------------------------------------

app = Flask(__name__)

CORS(app)
# ---------------------------------------------------------
# LOGGING
# ---------------------------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("f11-ai")


# ---------------------------------------------------------
# OPENAI
# ---------------------------------------------------------

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY is not configured")

client = OpenAI(api_key=OPENAI_API_KEY)


MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


# ---------------------------------------------------------
# SYSTEM PROMPT
# ---------------------------------------------------------

SYSTEM_PROMPT = """
You are F11 AI, the financial intelligence assistant inside the F11
investment application.

You help users understand:

- Indian stocks
- US stocks
- stock prices
- company fundamentals
- valuation
- P/E
- market capitalization
- beta
- volatility
- 52-week high and low
- portfolio information
- investment concepts
- market trends
- investment risk

IMPORTANT FINANCIAL DATA RULES:

1. NEVER invent a stock price.
2. NEVER invent market capitalization.
3. NEVER invent P/E, beta, volatility or other financial metrics.
4. When the user asks about a specific stock/company/ticker, ALWAYS
   use the get_stock_info tool.
5. If the tool cannot find the stock, clearly say that the F11 data
   source could not identify it.
6. Do not substitute a guessed ticker.
7. Distinguish between current/live data and historical data.
8. Always mention the data timestamp/source when available.
9. Do not guarantee investment returns.
10. Do not present investment advice as certainty.

Your answer should be:

- clear
- analytical
- concise
- data-driven
- understandable to a non-expert investor

For stock questions, structure the response approximately as:

Company / Ticker
Current Price
Market Capitalization
P/E
52-week range
Other available metrics

Then provide a short interpretation.

If a metric is unavailable, say "Not available" rather than guessing.
"""


# ---------------------------------------------------------
# TOOL DEFINITION
# ---------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_stock_info",
            "description": """
Retrieve verified F11 stock information.

Use this function whenever the user asks about:
- a stock
- a ticker
- a company
- current price
- market price
- market capitalization
- P/E
- beta
- volatility
- 52-week high
- 52-week low
- stock fundamentals
- stock valuation

Never answer these questions using model knowledge alone.
""",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Ticker symbol or company name, "
                            "for example RELIANCE, TCS, INFY, AAPL"
                        ),
                    }
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    }
]


# ---------------------------------------------------------
# TOOL EXECUTION
# ---------------------------------------------------------

def execute_tool(name, arguments):

    if name != "get_stock_info":
        return {
            "success": False,
            "error": "Unknown tool"
        }

    query = arguments.get("query", "").strip()

    if not query:
        return {
            "success": False,
            "error": "Empty stock query"
        }

    try:

        result = get_stock_info(query)

        if result is None:

            return {
                "success": False,
                "query": query,
                "error": "Stock not found"
            }

        return {
            "success": True,
            "query": query,
            "data": result,
            "retrieved_at": datetime.now(
                timezone.utc
            ).isoformat()
        }

    except Exception as exc:

        logger.exception(
            "Stock API error for query=%s",
            query
        )

        return {
            "success": False,
            "query": query,
            "error": "Market data provider unavailable"
        }


# ---------------------------------------------------------
# HEALTH CHECK
# ---------------------------------------------------------

@app.route("/health", methods=["GET"])
def health():

    return jsonify({
        "status": "ok",
        "service": "F11 AI",
        "model": MODEL,
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat()
    })


# ---------------------------------------------------------
# FRONTEND
# ---------------------------------------------------------

@app.route("/", methods=["GET"])
def home():

    return render_template("index.html")


# ---------------------------------------------------------
# CHAT API
# ---------------------------------------------------------

@app.route("/api/chat", methods=["POST", "OPTIONS"])
def chat():

    if request.method == "OPTIONS":
        return "", 204

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
                "response": "Please enter a question."
            }), 400


        # -------------------------------------------------
        # FIRST MODEL CALL
        # -------------------------------------------------

        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": user_message
            }
        ]


        response = client.chat.completions.create(

            model=MODEL,

            messages=messages,

            tools=TOOLS,

            tool_choice="auto",

            temperature=0.1
        )


        assistant_message = response.choices[0].message


        # -------------------------------------------------
        # TOOL CALL
        # -------------------------------------------------

        if assistant_message.tool_calls:

            messages.append(assistant_message)


            for tool_call in assistant_message.tool_calls:

                try:

                    arguments = json.loads(
                        tool_call.function.arguments
                    )

                except Exception:

                    arguments = {}


                tool_result = execute_tool(
                    tool_call.function.name,
                    arguments
                )


                messages.append({

                    "role": "tool",

                    "tool_call_id":
                        tool_call.id,

                    "content":
                        json.dumps(
                            tool_result,
                            default=str
                        )
                })


            # -------------------------------------------------
            # SECOND MODEL CALL
            # -------------------------------------------------

            final_response = client.chat.completions.create(

                model=MODEL,

                messages=messages,

                temperature=0.1
            )


            answer = (
                final_response
                .choices[0]
                .message
                .content
            )


            return jsonify({

                "success": True,

                "response": answer,

                "tool_used": True,

                "timestamp":
                    datetime.now(
                        timezone.utc
                    ).isoformat()
            })


        # -------------------------------------------------
        # NORMAL QUESTION
        # -------------------------------------------------

        answer = assistant_message.content or ""

        return jsonify({

            "success": True,

            "response": answer,

            "tool_used": False,

            "timestamp":
                datetime.now(
                    timezone.utc
                ).isoformat()
        })


    except Exception as exc:

        logger.exception(
            "F11 AI request failed"
        )

        return jsonify({

            "success": False,

            "response": (
                "F11 AI is temporarily unavailable. "
                "Please try again."
            ),

            "error": str(exc)
            if app.debug else None

        }), 500


# ---------------------------------------------------------
# PRODUCTION ENTRY POINT
# ---------------------------------------------------------

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            "10000"
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )

