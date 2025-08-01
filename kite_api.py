from kiteconnect import KiteConnect
from retrying import retry
import logging
from dotenv import load_dotenv
import os
from generate_token import generate_new_access_token
import asyncio
from utils import send_alert

load_dotenv()
logging.basicConfig(level=logging.INFO, filename='logs/daily_log.csv', format='%(asctime)s,%(levelname)s,%(message)s')

kite = KiteConnect(api_key=os.getenv('KITE_API_KEY'))
kite.set_access_token(os.getenv('KITE_ACCESS_TOKEN'))

api_call_count = 0
def increment_api_call():
    global api_call_count
    api_call_count += 1
    if api_call_count % 100 == 0:
        logging.warning(f"API calls nearing limit: {api_call_count}")
        asyncio.run(send_alert(f"Kite API calls nearing limit: {api_call_count}", error=True))

def refresh_access_token():
    try:
        new_token = generate_new_access_token()
        kite.set_access_token(new_token)
        with open('.env', 'r') as f:
            lines = f.readlines()
        with open('.env', 'w') as f:
            for line in lines:
                if line.startswith('KITE_ACCESS_TOKEN'):
                    f.write(f"KITE_ACCESS_TOKEN={new_token}\n")
                else:
                    f.write(line)
        logging.info("Access token refreshed successfully")
    except Exception as e:
        logging.error(f"Failed to refresh access token: {e}")
        asyncio.run(send_alert(f"Failed to refresh access token: {e}", error=True))

@retry(stop_max_attempt_number=3, wait_fixed=2000)
def fetch_market_tick(symbol='NSE:RELIANCE'):
    try:
        increment_api_call()
        quote = kite.ltp(symbol)[symbol]
        return {
            'symbol': symbol.split(':')[1],
            'open': quote['ohlc']['open'],
            'high': quote['ohlc']['high'],
            'low': quote['ohlc']['low'],
            'close': quote['last_price'],
            'volume': quote['volume']
        }
    except Exception as e:
        logging.error(f"Kite API error for {symbol}: {e}")
        asyncio.run(send_alert(f"Kite API error for {symbol}: {e}", error=True))
        if "Invalid access token" in str(e):
            refresh_access_token()
            return fetch_market_tick(symbol)
        raise

@retry(stop_max_attempt_number=3, wait_fixed=2000)
def fetch_market_ticks():
    from data_fetcher import get_nifty100_symbols
    from utils import load_excluded_stocks
    symbols = [f'NSE:{s}' for s in get_nifty100_symbols() if s not in load_excluded_stocks()]
    try:
        increment_api_call()
        quotes = kite.ltp(symbols)
        ticks = {}
        for symbol in symbols:
            quote = quotes[symbol]
            ticks[symbol.split(':')[1]] = {
                'symbol': symbol.split(':')[1],
                'open': quote['ohlc']['open'],
                'high': quote['ohlc']['high'],
                'low': quote['ohlc']['low'],
                'close': quote['last_price'],
                'volume': quote['volume']
            }
        return ticks
    except Exception as e:
        logging.error(f"Kite API error in fetch_market_ticks: {e}")
        asyncio.run(send_alert(f"Kite API error in fetch_market_ticks: {e}", error=True))
        if "Invalid access token" in str(e):
            refresh_access_token()
            return fetch_market_ticks()
        raise
