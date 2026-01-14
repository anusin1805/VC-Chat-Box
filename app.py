from flask import Flask, render_template, request, jsonify
from finance_api import get_stock_info
import re

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('chat.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json.get('message', '').strip()
    
    if not user_message:
        return jsonify({"response": "Please say something!"})

    # 1. Regex to find "Price of X" or "Stock X"
    match = re.search(r'\b(price|stock|check|of|for)\b\s*([A-Za-z0-9.$]+)', user_message, re.IGNORECASE)
    
    if match:
        # If user says "Price of $TSLA", extracted is "$TSLA"
        query = match.group(2)
    else:
        # If no keywords, take the first word (e.g., input "TSLA" -> query "TSLA")
        # Split by spaces to handle "TSLA please"
        query = user_message.split()[0]

    # 2. Pass to Finance API (which cleans $ and quotes)
    data = get_stock_info(query)
    
    if data:
        icon = "📑" if data['source'] == "Google Sheet" else "🌐"
        bot_response = (
            f"{icon} **{data['source']}**<br>"
            f"Symbol: {data['symbol']}<br>"
            f"Price: {data['price']}<br>"
            f"Change: {data['change']}"
        )
    else:
        # Helpful error message
        bot_response = (
            f"I couldn't find **{query}** in the sheet or live market.<br>"
            "Try checking the spelling or use a valid ticker (e.g., AAPL)."
        )

    return jsonify({"response": bot_response})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
