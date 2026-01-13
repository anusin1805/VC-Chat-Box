import yfinance as yf

def get_stock_info(ticker_symbol):
    """
    Fetches real-time stock data for a given symbol (e.g., AAPL, GOOGL).
    Integrates functionality from the googlefinance-API concept.
    """
    try:
        # Clean the input (remove spaces, ensure uppercase)
        ticker_symbol = ticker_symbol.strip().upper()
        
        # Fetch data using yfinance (reliable alternative to raw scraping)
        stock = yf.Ticker(ticker_symbol)
        
        # Get fast info
        info = stock.fast_info
        current_price = info.last_price
        prev_close = info.previous_close
        
        if current_price is None:
            return None

        # Calculate change
        change = current_price - prev_close
        change_percent = (change / prev_close) * 100

        # Format the result nicely for the chat
        result = {
            "symbol": ticker_symbol,
            "price": f"${current_price:,.2f}",
            "change": f"{change:+.2f} ({change_percent:+.2f}%)",
            "status": "success"
        }
        return result

    except Exception as e:
        print(f"API Error: {e}")
        return None
