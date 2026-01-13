from flask import Flask, render_template, request, jsonify
from finance_api import get_stock_info # Import the integration module
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

    # --- INTEGRATION LOGIC ---
    # Check if the user is asking for a stock price
    # Patterns: "price of AAPL", "stock TSLA", "check MSFT"
    stock_pattern = re.search(r'\b(price|stock|check|value)\b.*\b([A-Z]{1,5})\b', user_message, re.IGNORECASE)
    
    # Also check for direct symbols like "$AAPL" or just "GOOG" if it looks like a ticker
    direct_symbol = re.search(r'\$([A-Z]{1,5})', user_message)

    ticker = None
    if stock_pattern:
        ticker = stock_pattern.group(2) # Extract the symbol (e.g., AAPL)
    elif direct_symbol:
        ticker = direct_symbol.group(1)

    # If a ticker was found, call the Finance API
    if ticker:
        data = get_stock_info(ticker)
        if data:
            bot_response = (
                f"📈 **Market Data for {data['symbol']}**<br>"
                f"Current Price: {data['price']}<br>"
                f"Day Change: {data['change']}"
            )
        else:
            bot_response = f"I tried to check **{ticker}**, but I couldn't find data for that symbol."
    else:
        # Fallback for non-financial queries (General Chat Logic)
        bot_response = "I am the VC Finance Bot. Ask me about stock prices (e.g., 'Price of AAPL' or '$TSLA')."

    return jsonify({"response": bot_response})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
