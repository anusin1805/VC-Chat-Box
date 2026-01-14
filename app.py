@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json.get('message', '').strip()
    
    # Logic to extract the symbol (e.g., from "Price of TSLA" or "$AAPL")
    match = re.search(r'\b(price|stock|check|of)\b\s*([A-Za-z0-9.]{1,10})', user_message, re.IGNORECASE)
    ticker = match.group(2).upper() if match else None

    if ticker:
        data = get_stock_info(ticker) # This function now checks BOTH sources
        
        if data:
            source_tag = "🏢 **Internal Design Database**" if data['source'] == "Custom Sheet" else "🌐 **Live Exchange Data**"
            bot_response = (
                f"{source_tag}<br>"
                f"**{data['symbol']}**<br>"
                f"Price: {data['price']}<br>"
                f"Change: {data['change']}"
            )
        else:
            bot_response = f"I'm sorry, I couldn't find **{ticker}** in our catalog or the live market."
    else:
        bot_response = "Ask me for a price! E.g., 'Price of TSLA' or 'Check AAPL'."

    return jsonify({"response": bot_response})
