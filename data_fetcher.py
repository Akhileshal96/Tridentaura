import pandas as pd
import logging
from kiteconnect import KiteConnect
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange
from datetime import datetime, timedelta
from retrying import retry
import os
import requests
from utils import load_excluded_stocks, send_alert
from dotenv import load_dotenv
import asyncio

load_dotenv()
logging.basicConfig(level=logging.INFO, filename='logs/daily_log.csv', format='%(asctime)s,%(levelname)s,%(message)s')

kite = KiteConnect(api_key=os.getenv('KITE_API_KEY'))
kite.set_access_token(os.getenv('KITE_ACCESS_TOKEN'))

@retry(stop_max_attempt_number=3, wait_exponential_multiplier=1000, wait_exponential_max=10000)
def get_nifty100_symbols():
    try:
        url = "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20100"
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
        symbols = [item['symbol'] for item in data['data']]
        logging.info(f"Fetched NIFTY 100 symbols from NSE: {len(symbols)} symbols")
        return symbols
    except Exception as e:
        logging.error(f"Error fetching NIFTY 100 symbols: {e}")
        asyncio.run(send_alert(f"Error fetching NIFTY 100 symbols: {e}", error=True))
        logging.warning("Using fallback NIFTY 100 symbols")
        return ['RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'HINDUNILVR', 'ICICIBANK', 'SBIN']

def calculate_indicators(df):
    df['ema_fast'] = EMAIndicator(df['close'], window=12).ema_indicator()
    df['ema_slow'] = EMAIndicator(df['close'], window=26).ema_indicator()
    df['rsi'] = RSIIndicator(df['close'], window=14).rsi()
    macd = MACD(df['close'])
    df['macd'] = macd.macd()
    df['atr'] = AverageTrueRange(df['high'], df['low'], df['close'], window=14).average_true_range()
    return df

@retry(stop_max_attempt_number=3, wait_fixed=2000)
def fetch_nifty100_data(start_date=None, end_date=None, save_to_csv=True):
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')

    symbols = [s for s in get_nifty100_symbols() if s not in load_excluded_stocks()]
    all_data = []

    for symbol in symbols:
        try:
            instrument_token = kite.ltp(f'NSE:{symbol}')[f'NSE:{symbol}']['instrument_token']
            data = kite.historical_data(
                instrument_token=instrument_token,
                from_date=start_date,
                to_date=end_date,
                interval='minute'
            )
            df = pd.DataFrame(data)
            if df.empty:
                logging.warning(f"No data for {symbol}")
                continue
            df['symbol'] = symbol
            df = df.rename(columns={'date': 'timestamp', 'open': 'open', 'high': 'high', 'low': 'low', 'close': 'close', 'volume': 'volume'})
            df = calculate_indicators(df)
            all_data.append(df)
        except Exception as e:
            logging.error(f"Error fetching historical data for {symbol}: {e}")
            asyncio.run(send_alert(f"Error fetching historical data for {symbol}: {e}", error=True))

    if not all_data:
        raise ValueError("No data fetched for any NIFTY 100 stocks")

    combined_df = pd.concat(all_data, ignore_index=True)

    if save_to_csv:
        os.makedirs('data', exist_ok=True)
        combined_df.to_csv('data/nifty100.csv', index=False)
        logging.info("Updated data/nifty100.csv")

    return combined_df

@retry(stop_max_attempt_number=3, wait_fixed=2000)
def fetch_nifty100_realtime():
    symbols = [s for s in get_nifty100_symbols() if s not in load_excluded_stocks()]
    ticks = {}
    try:
        quotes = kite.ltp([f'NSE:{s}' for s in symbols])
        for symbol in symbols:
            quote = quotes[f'NSE:{symbol}']
            ticks[symbol] = {
                'symbol': symbol,
                'open': quote['ohlc']['open'],
                'high': quote['ohlc']['high'],
                'low': quote['ohlc']['low'],
                'close': quote['last_price'],
                'volume': quote['volume']
            }
            recent_data = kite.historical_data(
                instrument_token=quote['instrument_token'],
                from_date=(datetime.now() - timedelta(minutes=50)).strftime('%Y-%m-%d %H:%M:%S'),
                to_date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                interval='minute'
            )
            df = pd.DataFrame(recent_data)
            if not df.empty:
                df = calculate_indicators(df)
                ticks[symbol].update({
                    'ema_fast': df['ema_fast'].iloc[-1] if not df['ema_fast'].isna().iloc[-1] else 0.0,
                    'ema_slow': df['ema_slow'].iloc[-1] if not df['ema_slow'].isna().iloc[-1] else 0.0,
                    'rsi': df['rsi'].iloc[-1] if not df['rsi'].isna().iloc[-1] else 0.0,
                    'macd': df['macd'].iloc[-1] if not df['macd'].isna().iloc[-1] else 0.0,
                    'atr': df['atr'].iloc[-1] if not df['atr'].isna().iloc[-1] else 0.0
                })
    except Exception as e:
        logging.error(f"Error fetching real-time data: {e}")
        asyncio.run(send_alert(f"Error fetching real-time data: {e}", error=True))
    return ticks
