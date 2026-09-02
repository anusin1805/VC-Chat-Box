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

    query_clean = str(query).upper().replace('$', '').replace("'", "").replace('"', '').strip()
    
    # Strip suffixes so "RELIANCE.NS" matches "RELIANCE" in your Google Sheet
    sheet_query = query_clean.replace('.NS', '').replace('.BO', '')
    
    # ----------------------------------------------------
    # 1. TRY GOOGLE SHEET SEARCH (Fuzzy Match across columns)
    # ----------------------------------------------------
    try:
        # INCREASED TIMEOUT: Render free tier requires more time for external downloads
        response = requests.get(CSV_URL, timeout=15)
        
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
            
            # Clean hidden spaces from column headers
            df.columns = df.columns.str.strip()
            
            # Use regex=False to prevent punctuation from breaking the search
            mask = df.apply(lambda row: row.astype(str).str.contains(sheet_query, case=False, regex=False, na=False).any(), axis=1)
            result = df[mask]

            if not result.empty:
                row = result.iloc[0].to_dict()
                
                # Fetch key values with fallback logic
                symbol = row.get('Ticker Symbol', row.get('Ticker', row.get('Symbol', sheet_query)))
                price = row.get('Close', row.get('Price', row.get('NAV', 'N/A')))
                change = row.get('% Change', row.get('Change', 'N/A'))
                
                return f"<b>{symbol}</b> (Google Sheet)<br>Price: <b>₹{price}</b> | Change: {change}"
    except requests.exceptions.Timeout:
        print("Sheet Error: Timed out waiting for Google Sheets.")
    except Exception as e:
        print(f"Sheet Error: {e}")

    # ----------------------------------------------------
    # 2. TRY YAHOO FINANCE (Supports US & Indian Tickers)
    # ----------------------------------------------------
    ticker_candidates = [
        query_clean,
        f"{query_clean}.NS", 
        f"{query_clean}.BO"   
    ]

    for ticker_symbol in ticker_candidates:
        try:
            # Spoof user-agent to bypass Yahoo's block on Render IPs
            session = requests.Session()
            session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            
            ticker = yf.Ticker(ticker_symbol, session=session)
            
            # Use history instead of fast_info for better cloud reliability
            hist = ticker.history(period="1d")
            
            if not hist.empty:
                price = hist['Close'].iloc[-1]
                currency = ticker.info.get('currency', 'USD')
                curr_symbol = "₹" if currency == "INR" else "$"
                return f"<b>{ticker_symbol}</b> (Live Market)<br>Price: <b>{curr_symbol}{price:.2f}</b>"
        except Exception as e:
            print(f"yfinance error for {ticker_symbol}: {e}")
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

