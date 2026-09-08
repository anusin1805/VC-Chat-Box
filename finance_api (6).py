import pandas as pd
import io
import requests
import re
import time
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError, as_completed
import yfinance as yf
from openai import OpenAI
from google import genai
import os

logger = logging.getLogger("f11-ai.finance_api")

SHEET_ID = "11MvFhyIdRI6dxLn4jGi27Inp0iPfD-Ce"
GID = "1760617300"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"

api_key = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None

gemini_api_key = os.environ.get("GEMINI_API_KEY")
gemini_fallback_client = genai.Client(api_key=gemini_api_key) if gemini_api_key else None

# ----------------------------------------------------
# ONE OVERALL BUDGET for the entire lookup (all steps combined).
# Gemini's automatic function calling can invoke get_stock_info more than
# once per chat request, so each individual call must stay well under both
# gunicorn's worker timeout AND Render's own proxy timeout in front of it.
# ----------------------------------------------------
OVERALL_BUDGET = 14.0
SHEET_TIMEOUT = 4
YF_TOTAL_TIMEOUT = 5  # all 3 candidates run in parallel, capped together
AI_FALLBACK_TIMEOUT = 4

_executor = ThreadPoolExecutor(max_workers=6)


def _run_with_timeout(fn, timeout, *args, **kwargs):
    """Run fn in a worker thread and hard-cancel it (from the caller's
    perspective) if it doesn't finish within `timeout` seconds.
    This protects us even when the underlying library (yfinance, requests)
    doesn't respect its own timeout argument.
    """
    if timeout <= 0:
        return None
    future = _executor.submit(fn, *args, **kwargs)
    try:
        return future.result(timeout=timeout)
    except FutureTimeoutError:
        logger.warning(f"{fn.__name__} timed out after {timeout}s")
        return None
    except Exception as e:
        logger.warning(f"{fn.__name__} raised {e}")
        return None


def extract_symbol(user_input):
    """
    Cleans user input to reliably extract the ticker symbol without breaking on 'of' or '.NS'
    """
    if not user_input:
        return ""

    cleaned = re.sub(r'^(price\s+of\s+|price\s+|check\s+|show\s+|what\s+is\s+)', '', user_input, flags=re.IGNORECASE).strip()
    # FIXED: original regex r'[\$"'']' was broken by the unescaped apostrophe
    # inside the raw string and never actually stripped a plain apostrophe.
    cleaned = re.sub(r'[\$"\']', '', cleaned).strip()
    return cleaned


def _fetch_sheet_csv():
    response = requests.get(CSV_URL, timeout=SHEET_TIMEOUT)
    response.raise_for_status()
    return pd.read_csv(io.StringIO(response.content.decode('utf-8')))


def _lookup_sheet(sheet_query):
    df = _run_with_timeout(_fetch_sheet_csv, SHEET_TIMEOUT)
    if df is None:
        return None

    df.columns = df.columns.str.strip()
    mask = df.apply(lambda row: row.astype(str).str.contains(sheet_query, case=False, regex=False, na=False).any(), axis=1)
    result = df[mask]

    if result.empty:
        return None

    row = result.iloc[0].to_dict()

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


def _fetch_yf_price(ticker_symbol):
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    ticker = yf.Ticker(ticker_symbol, session=session)
    hist = ticker.history(period="1d")

    if hist.empty:
        return None

    price = hist['Close'].iloc[-1]
    try:
        currency = ticker.info.get('currency', 'USD')
    except Exception:
        currency = 'USD'
    curr_symbol = "₹" if currency == "INR" else "$"
    return f"<b>{ticker_symbol}</b> (Live Market)<br>Price: <b>{curr_symbol}{price:.2f}</b>"


def _lookup_yfinance(query_upper, sheet_query, timeout):
    """Try all 3 ticker candidates in parallel, return the first success.
    Bounded by `timeout` regardless of how many candidates there are.
    """
    if timeout <= 0:
        return None

    ticker_candidates = [
        query_upper,
        f"{sheet_query}.NS",
        f"{sheet_query}.BO",
    ]
    futures = {_executor.submit(_fetch_yf_price, t): t for t in ticker_candidates}
    deadline = time.monotonic() + timeout
    result = None
    try:
        for future in as_completed(futures, timeout=timeout):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                value = future.result(timeout=max(remaining, 0))
            except Exception:
                continue
            if value:
                result = value
                break
    except FutureTimeoutError:
        pass
    return result


def _fetch_gemini_fallback(ticker_query):
    response = gemini_fallback_client.models.generate_content(
        model='gemini-3.6-flash',
        contents=f"Provide current stock info for: {ticker_query}. Be concise.",
        config={
            "system_instruction": "You are a finance assistant. Provide stock information concisely.",
            "temperature": 0.1,
        }
    )
    return response.text


def _fetch_openai_fallback(ticker_query):
    completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a finance assistant. Provide stock information concisely."},
            {"role": "user", "content": f"Provide stock info for: {ticker_query}"}
        ],
        max_tokens=150
    )
    return completion.choices[0].message.content


def get_stock_info(user_input):
    start = time.monotonic()
    deadline = start + OVERALL_BUDGET
    ticker_query = extract_symbol(user_input)

    if not ticker_query:
        return "Please enter a valid stock ticker or company name."

    query_upper = ticker_query.upper()
    sheet_query = query_upper.replace('.NS', '').replace('.BO', '')

    def remaining():
        return deadline - time.monotonic()

    # 1. GOOGLE SHEET LOOKUP
    sheet_result = _lookup_sheet(sheet_query) if remaining() > 0 else None
    if sheet_result:
        logger.info(f"[{ticker_query}] resolved via sheet in {time.monotonic()-start:.2f}s")
        return sheet_result

    # 2. YAHOO FINANCE LOOKUP (all candidates in parallel, one shared timeout)
    yf_budget = min(YF_TOTAL_TIMEOUT, remaining())
    yf_result = _lookup_yfinance(query_upper, sheet_query, yf_budget) if yf_budget > 0 else None
    if yf_result:
        logger.info(f"[{ticker_query}] resolved via yfinance in {time.monotonic()-start:.2f}s")
        return yf_result

    # 3. GEMINI AI FALLBACK — tried first since GEMINI_API_KEY is already
    #    required for the chat itself, so this needs no extra key.
    if gemini_fallback_client and remaining() > 0:
        budget = min(AI_FALLBACK_TIMEOUT, remaining())
        gemini_result = _run_with_timeout(_fetch_gemini_fallback, budget, ticker_query)
        if gemini_result:
            logger.info(f"[{ticker_query}] resolved via Gemini fallback in {time.monotonic()-start:.2f}s")
            return gemini_result

    # 4. OPENAI AI FALLBACK (only runs if OPENAI_API_KEY is set and budget remains)
    if client and remaining() > 0:
        budget = min(AI_FALLBACK_TIMEOUT, remaining())
        ai_result = _run_with_timeout(_fetch_openai_fallback, budget, ticker_query)
        if ai_result:
            logger.info(f"[{ticker_query}] resolved via OpenAI fallback in {time.monotonic()-start:.2f}s")
            return ai_result

    logger.info(f"[{ticker_query}] no data found after {time.monotonic()-start:.2f}s")
    return f"Could not find stock data for <b>{ticker_query}</b>. Try searching using exact tickers like <b>RELIANCE.NS</b> or <b>TSLA</b>."
