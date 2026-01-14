import pandas as pd
import io
import requests
import yfinance as yf

# Your Google Sheet Settings
SHEET_ID = "1YGNIxeDVD0FyO0shvhL_AQ0gcM9qaXEoN8lyyXWaf_s"
GID = "501687"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"

def get_stock_info(query):
    query_clean = query.strip().upper()
    
    # --- SOURCE 1: Try your Google Sheet ---
    try:
        response = requests.get(CSV_URL, timeout=10)
        df = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
        
        # Mapping your specific headers:
        # "Ticker Symbol" -> used for searching
        # "Close" -> used for price
        # "% Change" -> used for change
        
        # Standardize column names for easy searching
        df.columns = [c.strip() for c in df.columns]

        # Search the 'Ticker Symbol' column
        result = df[df['Ticker Symbol'].astype(str).str.upper() == query_clean]
        
        if not result.empty:
            row = result.iloc[0]
            return {
                "source": "Google Sheet",
                "symbol": row['Ticker Symbol'],
                "price": f"${row['Close']:.2f}" if isinstance(row['Close'], (int, float)) else str(row['Close']),
                "change": str(row.get('% Change', '0.00%'))
            }
    except Exception as e:
        print(f"Sheet Search Error: {e}")

    # --- SOURCE 2: Live Market Fallback (yfinance) ---
    try:
        ticker = yf.Ticker(query_clean)
        # yfinance handles names like "Tesla" better than raw CSVs
        info = ticker.fast_info
        if info.last_price is not None:
            return {
                "source": "Live Market",
                "symbol": query_clean,
                "price": f"${info.last_price:.2f}",
                "change": f"{((info.last_price - info.previous_close)/info.previous_close)*100:+.2f}%"
            }
    except:
        pass

    return None
