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
    
    # --- SOURCE 1: Try Google Sheet ---
    try:
        response = requests.get(CSV_URL, timeout=10)
        df = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
        # Clean column names
        df.columns = [c.strip().upper() for c in df.columns]

        # Search by Symbol (TSLA) OR by Company Name (Tesla)
        mask = (df['SYMBOL'].astype(str).str.upper() == query_clean)
        if 'COMPANY' in df.columns:
            mask |= (df['COMPANY'].astype(str).str.upper().str.contains(query_clean))
        
        result = df[mask]

        if not result.empty:
            row = result.iloc[0]
            return {
                "source": "Google Sheet",
                "symbol": row.get('SYMBOL', query_clean),
                "price": str(row.get('PRICE', 'N/A')),
                "change": str(row.get('CHANGE', '0.00%'))
            }
    except Exception as e:
        print(f"Sheet Error: {e}")

    # --- SOURCE 2: Try Live Market (Backup) ---
    try:
        # yfinance is great at handling "Tesla" or "TSLA"
        ticker = yf.Ticker(query_clean)
        info = ticker.fast_info
        if info.last_price is not None and not pd.isna(info.last_price):
            return {
                "source": "Live Market",
                "symbol": query_clean,
                "price": f"${info.last_price:.2f}",
                "change": f"{((info.last_price - info.previous_close)/info.previous_close)*100:+.2f}%"
            }
    except:
        pass

    return None
