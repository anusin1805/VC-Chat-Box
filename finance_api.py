import pandas as pd
import io
import requests
import re
import yfinance as yf
from openai import OpenAI
import os

SHEET_ID = "11MvFhyIdRI6dxLn4jGi27Inp0iPfD-Ce"
GID = "1760617300"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"

api_key = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None

def extract_symbol(user_input):
    """
    Cleans user input to reliably extract the ticker symbol without breaking on 'of' or '.NS'
    """
    if not user_input:
        return ""
    
    # Strip conversational prefixes
    cleaned = re.sub(r'^(price\s+of\s+|price\s+|check\s+|show\s+|what\s+is\s+)', '', user_input, flags=re.IGNORECASE).strip()
    # Remove clutter characters
    cleaned = re.sub(r'[\$"'']', '', cleaned).strip()
    return cleaned

def get_stock_info(user_input):
    ticker_query = extract_symbol(user_input)
    
    if not ticker_query:
        return "Please enter a valid stock ticker or company name."

    # Normalized query for matching
    query_upper = ticker_query.upper()
    sheet_query = query_upper.replace('.NS', '').replace('.BO', '')

    # ----------------------------------------------------
    # 1. GOOGLE SHEET LOOKUP
    # ----------------------------------------------------
    try:
        response = requests.get(CSV_URL, timeout=15)
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
            
            # Clean and normalize column names (remove hidden spaces & lowercase)
            df.columns = df.columns.str.strip()
            
            # Partial/Fuzzy match across all columns
            mask = df.apply(lambda row: row.astype(str).str.contains(sheet_query, case=False, regex=False, na=False).any(), axis=1)
            result = df[mask]

            if not result.empty:
                row = result.iloc[0].to_dict()
                
                # Dynamic column name lookup to prevent "Check CSV column headers" errors
                def find_val(keys, default='N/A'):
                    for k in keys:
                        for col in row.keys():
                            if k.lower() == col.lower():
                                return row[col]
                    return default

                symbol = find_val(['Ticker Symbol', 'Ticker', 'Symbol', 'Name'], sheet_query)
                price = find_val(['Close', 'Price', 'NAV', 'LTP', 'Last Price'])
                change = find_val(['% Change', 'Change', 'Chg%'])

                return f"<b>{symbol}</b> (Google Sheet)<br>Price: <b>₹{price}</b> | Change: {change}"
    except Exception as e:
        print(f"Sheet Search Error: {e}")

    # ----------------------------------------------------
    # 2. YAHOO FINANCE LOOKUP (Live Market)
    # ----------------------------------------------------
    ticker_candidates = [
        query_upper,
        f"{sheet_query}.NS",  # NSE India fallback
        f"{sheet_query}.BO"   # BSE India fallback
    ]

    for ticker_symbol in ticker_candidates:
        try:
            session = requests.Session()
            session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            
            ticker = yf.Ticker(ticker_symbol, session=session)
            hist = ticker.history(period="1d")
            
            if not hist.empty:
                price = hist['Close'].iloc[-1]
                currency = ticker.info.get('currency', 'USD')
                curr_symbol = "₹" if currency == "INR" else "$"
                return f"<b>{ticker_symbol}</b> (Live Market)<br>Price: <b>{curr_symbol}{price:.2f}</b>"
        except Exception:
            continue

    # ----------------------------------------------------
    # 3. OPENAI AI FALLBACK
    # ----------------------------------------------------
    if client:
        try:
            completion = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a finance assistant. Provide stock information concisely."},
                    {"role": "user", "content": f"Provide stock info for: {ticker_query}"}
                ],
                max_tokens=150
            )
            return completion.choices[0].message.content
        except Exception as e:
            print(f"OpenAI Error: {e}")

    return f"Could not find stock data for <b>{ticker_query}</b>. Try searching using exact tickers like <b>RELIANCE.NS</b> or <b>TSLA</b>."
