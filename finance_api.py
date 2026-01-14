import pandas as pd
import io
import requests
import yfinance as yf

# Your Google Sheet Settings
SHEET_ID = "1YGNIxeDVD0FyO0shvhL_AQ0gcM9qaXEoN8lyyXWaf_s"
GID = "501687"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"

def get_stock_info(query):
    query = query.strip().upper()
    
    # --- SOURCE 1: Try Google Sheet (Custom Data) ---
    try:
        response = requests.get(CSV_URL, timeout=10)
        df = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
        df.columns = [c.strip().upper() for c in df.columns]

        # Search for symbol in your sheet
        sheet_result = df[df['SYMBOL'] == query]
        if not sheet_result.empty:
            row = sheet_result.iloc[0]
            return {
                "source": "Custom Sheet",
                "symbol": row.get('SYMBOL', query),
                "price": str(row.get('PRICE', 'N/A')),
                "change": str(row.get('CHANGE', '0.00%'))
            }
    except Exception as e:
        print(f"Sheet Access Error: {e}")

    # --- SOURCE 2: Fallback to Live Market (yfinance) ---
    try:
        stock = yf.Ticker(query)
        info = stock.fast_info
        if info.last_price is not None:
            price = info.last_price
            change_val = price - info.previous_close
            change_pct = (change_val / info.previous_close) * 100
            
            return {
                "source": "Live Market",
                "symbol": query,
                "price": f"${price:,.2f}",
                "change": f"{change_pct:+.2f}%"
            }
    except Exception as e:
        print(f"Live Market Error: {e}")

    return None # Not found in either source
