import pandas as pd
import io
import requests
import yfinance as yf
from openai import OpenAI
import os

SHEET_ID = "11MvFhyIdRI6dxLn4jGi27Inp0iPfD-Ce"
GID = "1760617300"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"

# Pre-initialize OpenAI client if key exists
api_key = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None

def get_stock_info(query):
    if not query:
        return None

    query_clean = str(query).replace('$', '').replace("'", "").replace('"', '').strip()
    
    # ----------------------------------------------------
    # 1. TRY GOOGLE SHEET SEARCH (Fuzzy Match across columns)
    # ----------------------------------------------------
    try:
        response = requests.get(CSV_URL, timeout=5)
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
            
            # Global case-insensitive search across all text cells
            mask = df.apply(lambda row: row.astype(str).str.contains(query_clean, case=False, na=False).any(), axis=1)
            result = df[mask]

            if not result.empty:
                row = result.iloc[0].to_dict()
                # Dynamically fetch key values
                symbol = row.get('Ticker Symbol', row.get('Ticker', row.get('Symbol', query_clean.upper())))
                price = row.get('Close', row.get('Price', row.get('NAV', 'N/A')))
                change = row.get('% Change', row.get('Change', 'N/A'))
                
                return f"<b>{symbol}</b> (Google Sheet)<br>Price: <b>₹{price}</b> | Change: {change}"
    except Exception as e:
        print(f"Sheet Error: {e}")

    # ----------------------------------------------------
    # 2. TRY YAHOO FINANCE (Supports US & Indian Tickers)
    # ----------------------------------------------------
    # List of ticker variations to attempt (e.g., RELIANCE -> RELIANCE.NS)
    ticker_candidates = [
        query_clean.upper(),
        f"{query_clean.upper()}.NS",  # NSE India
        f"{query_clean.upper()}.BO"   # BSE India
    ]

    for ticker_symbol in ticker_candidates:
        try:
            ticker = yf.Ticker(ticker_symbol)
            info = ticker.fast_info
            price = getattr(info, 'last_price', None)
            
            if price is not None and not pd.isna(price):
                currency = getattr(info, 'currency', 'USD')
                curr_symbol = "₹" if currency == "INR" else "$"
                return f"<b>{ticker_symbol}</b> (Live Market)<br>Price: <b>{curr_symbol}{price:.2f}</b>"
        except Exception:
            continue

    # ----------------------------------------------------
    # 3. FALLBACK TO OPENAI AI RESPONSE
    # ----------------------------------------------------
    if client:
        try:
            completion = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a financial assistant. Give concise details about the requested stock/company."},
                    {"role": "user", "content": f"Provide current financial status, ticker details, and company profile for: {query_clean}"}
                ],
                max_tokens=150
            )
            return completion.choices[0].message.content
        except Exception as e:
            print(f"OpenAI Fallback Error: {e}")

    return f"Could not find stock info for <b>{query_clean}</b>. Try entering an explicit ticker like <b>RELIANCE.NS</b> or <b>TSLA</b>."
