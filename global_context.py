from kiteconnect import KiteConnect
from dotenv import load_dotenv
import os
import logging
import yfinance as yf
import requests
from retrying import retry
import asyncio
from utils import send_alert

load_dotenv()
logging.basicConfig(level=logging.INFO, filename='logs/daily_log.csv', format='%(asctime)s,%(levelname)s,%(message)s')

kite = KiteConnect(api_key=os.getenv('KITE_API_KEY'))
kite.set_access_token(os.getenv('KITE_ACCESS_TOKEN'))

@retry(stop_max_attempt_number=3, wait_exponential_multiplier=1000, wait_exponential_max=10000)
def fetch_nse_sector_indices():
    try:
        url = "https://www.nseindia.com/api/equity-stockIndices?index=SECTORAL%20INDICES"
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json',
            'Referer': 'https://www.nseindia.com'
        }
        session = requests.Session()
        session.get("https://www.nseindia.com", headers=headers)
        response = session.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        sector_data = {}
        for item in data['data']:
            sector_name = item['index']
            daily_return = item.get('percentChange', 0.0) / 100.0
            sector_data[sector_name] = daily_return
        sorted_sectors = sorted(sector_data.items(), key=lambda x: x[1], reverse=True)
        return {k: v for k, v in sorted_sectors}, sorted_sectors[:3]
    except Exception as e:
        logging.error(f"Error fetching NSE sector indices: {e}")
        asyncio.run(send_alert(f"Error fetching NSE sector indices: {e}", error=True))
        return {}, []

@retry(stop_max_attempt_number=3, wait_exponential_multiplier=1000, wait_exponential_max=10000)
def fetch_global_context():
    try:
        vix = kite.ltp('NSE:INDIAVIX')['NSE:INDIAVIX']['last_price']
        gift_nifty = yf.Ticker("^NIFTY50").history(period="1d")
        gift_nifty_change = ((gift_nifty['Close'].iloc[-1] - gift_nifty['Open'].iloc[-1]) / gift_nifty['Open'].iloc[-1]) if not gift_nifty.empty else 0.0
        us_futures = {
            'S&P 500': yf.Ticker("ES=F").history(period="1d"),
            'Nasdaq': yf.Ticker("NQ=F").history(period="1d"),
            'Dow': yf.Ticker("YM=F").history(period="1d")
        }
        us_futures_changes = {
            k: ((v['Close'].iloc[-1] - v['Open'].iloc[-1]) / v['Open'].iloc[-1]) if not v.empty else 0.0
            for k, v in us_futures.items()
        }
        asian_markets = {
            'Nikkei': yf.Ticker("^N225").history(period="1d"),
            'Hang Seng': yf.Ticker("^HSI").history(period="1d")
        }
        asian_markets_changes = {
            k: ((v['Close'].iloc[-1] - v['Open'].iloc[-1]) / v['Open'].iloc[-1]) if not v.empty else 0.0
            for k, v in asian_markets.items()
        }
        usdinr = yf.Ticker("INR=X").history(period="1d")
        usdinr_change = ((usdinr['Close'].iloc[-1] - usdinr['Open'].iloc[-1]) / usdinr['Open'].iloc[-1]) if not usdinr.empty else 0.0
        sector_data, top_sectors = fetch_nse_sector_indices()
        return {
            'india_vix': vix,
            'gift_nifty_change': gift_nifty_change,
            'us_futures_changes': us_futures_changes,
            'asian_markets_changes': asian_markets_changes,
            'usdinr_change': usdinr_change,
            'sector_strength': sector_data,
            'top_sectors': [s[0] for s in top_sectors]
        }
    except Exception as e:
        logging.error(f"Error fetching global context: {e}")
        asyncio.run(send_alert(f"Error fetching global context: {e}", error=True))
        return {
            'india_vix': 0.0,
            'gift_nifty_change': 0.0,
            'us_futures_changes': {'S&P 500': 0.0, 'Nasdaq': 0.0, 'Dow': 0.0},
            'asian_markets_changes': {'Nikkei': 0.0, 'Hang Seng': 0.0},
            'usdinr_change': 0.0,
            'sector_strength': {},
            'top_sectors': []
        }
