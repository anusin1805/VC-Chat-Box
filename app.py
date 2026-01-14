import re

@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json.get('message', '').strip()
    
    # Clean the message: extract just the ticker/name
    # This regex looks for "Price of TSLA" or just "TSLA"
    match = re.search(r'\b(price|stock|check|of|for)\b\s*([A-Za-z0-9.]{1,10})', user_message, re.IGNORECASE)
    
    if match:
        query = match.group(2)
    else:
        # If no keywords, just take the first word (e.g., user just typed "TSLA")
        query = user_message.split()[0]

    data = get_stock_info(query)
    
    if data:
        source_icon = "📑" if data['source'] == "Google Sheet" else "🌐"
        bot_response = (
            f"{source_icon} **{data['source']} Data**<br>"
            f"Symbol: {data['symbol']}<br>"
            f"Price: {data['price']}<br>"
            f"Change: {data['change']}"
        )
    else:
        bot_response = f"I couldn't find **{query}** in the spreadsheet or the market. Try a symbol like **TSLA**."

    return jsonify({"response": bot_response})
