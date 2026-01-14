@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json.get('message', '').strip()
    
    # regex to find the name/symbol after "Price of" or "Stock"
    match = re.search(r'\b(price|stock|check|of)\b\s*([A-Za-z0-9.]{1,10})', user_message, re.IGNORECASE)
    query = match.group(2) if match else user_message # Fallback to full message if no keywords
    
    data = get_stock_info(query)
    
    if data:
        # Highlight if it came from your sheet or the web
        header = "📑 **Sheet Data**" if data['source'] == "Google Sheet" else "🌐 **Live Data**"
        response = f"{header}<br>Symbol: {data['symbol']}<br>Price: {data['price']}<br>Change: {data['change']}"
    else:
        response = f"I couldn't find **{query}** in your spreadsheet or the stock market. Check the spelling?"

    return jsonify({"response": response})
