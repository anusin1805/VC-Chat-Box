import pandas as pd
import io
import requests
import yfinance as yf

# --- NEW SHEET CREDENTIALS ---
# From your URL: https://docs.google.com/spreadsheets/d/11MvFhyIdRI6dxLn4jGi27Inp0iPfD-Ce/edit?gid=1760617300
SHEET_ID = "11MvFhyIdRI6dxLn4jGi27Inp0iPfD-Ce"
GID = "1760617300"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"

# In finance_api.py, inside get_stock_info:

# 1. Force headers to lowercase and strip spaces to avoid mismatches
df.columns = [c.strip().lower() for c in df.columns]

# 2. Find the column that looks like 'ticker' or 'symbol'
ticker_col = next((c for c in df.columns if 'ticker' in c or 'symbol' in c), None)

if ticker_col:
    # Match against the cleaned query
    result = df[df[ticker_col].astype(str).str.upper() == query_clean]

def get_stock_info(query):
    # 1. CLEAN THE QUERY
    # Remove $, ', ", and spaces
    query_clean = query.replace('$', '').replace("'", "").replace('"', '').strip().upper()
    
    print(f"Searching for: {query_clean}") # Debug log for Render

    # --- SOURCE 1: Check Google Sheet ---
    try:
        response = requests.get(CSV_URL, timeout=10)
        response.raise_for_status()
        
        df = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
        
        # Clean column headers (strip spaces)
        df.columns = [c.strip() for c in df.columns]

        # Search Logic:
        # Check 'Ticker Symbol' column (e.g., TSLA)
        # OR Check 'Stock' column (e.g., Tesla) if it exists
        mask = (df['Ticker Symbol'].astype(str).str.upper() == query_clean)
        
        if 'Stock' in df.columns:
            mask |= (df['Stock'].astype(str).str.upper().str.contains(query_clean))
        
        result = df[mask]

        if not result.empty:
            row = result.iloc[0]
            # Handle potential missing/formatted data safely
            price_raw = row.get('Close', row.get('Price', 'N/A'))
            change_raw = row.get('% Change', row.get('Change', '0.00%'))
            
            return {
                "source": "Google Sheet",
                "symbol": row.get('Ticker Symbol', query_clean),
                "price": f"${price_raw}" if str(price_raw).replace('.','').isdigit() else str(price_raw),
                "change": str(change_raw)
            }
            
    except Exception as e:
        print(f"Sheet Error: {e}")

    # --- SOURCE 2: Live Market (Fallback) ---
    try:
        # Only try yfinance if the query looks like a ticker (short, no spaces)
        if len(query_clean) <= 5 and " " not in query_clean:
            ticker = yf.Ticker(query_clean)
            info = ticker.fast_info
            
            if info.last_price is not None:
                return {
                    "source": "Live Market",
                    "symbol": query_clean,
                    "price": f"${info.last_price:.2f}",
                    "change": "Live"
                }
    except Exception as e:
        print(f"Live API Error: {e}")

    return None
