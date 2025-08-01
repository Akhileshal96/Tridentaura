from data_fetcher import fetch_nifty100_realtime
from utils import send_alert
from risk_engine import force_exit_positions, allowed
from kiteconnect import KiteConnect
import asyncio
from global_context import fetch_global_context

def mock_kite_positions():
    return {
        'day': [
            {'tradingsymbol': 'RELIANCE', 'quantity': 50, 'pnl': 1000},
            {'tradingsymbol': 'TCS', 'quantity': -20, 'pnl': -500}
        ]
    }

def mock_kite_place_order(variety, exchange, tradingsymbol, transaction_type, quantity, product, order_type):
    print(f"Mock order: {transaction_type} {quantity} shares of {tradingsymbol}")

def mock_kite_ltp(symbol):
    return {symbol: {'instrument_token': 'mock_token', 'last_price': 15.0, 'ohlc': {'open': 14.5, 'high': 15.5, 'low': 14.0, 'close': 15.0}, 'volume': 100000}}

kite = KiteConnect(api_key="mock_key")
kite.positions = mock_kite_positions
kite.place_order = mock_kite_place_order
kite.ltp = mock_kite_ltp

def mock_fetch_nifty100_realtime():
    return {
        'RELIANCE': {
            'symbol': 'RELIANCE',
            'open': 3000.0,
            'high': 3050.0,
            'low': 2950.0,
            'close': 3020.0,
            'volume': 1000000,
            'ema_fast': 3010.0,
            'ema_slow': 3000.0,
            'rsi': 60.0,
            'macd': 10.0,
            'atr': 50.0
        }
    }

def mock_fetch_global_context():
    return {
        'india_vix': 15.0,
        'gift_nifty_change': 0.005,
        'us_futures_changes': {'S&P 500': 0.003, 'Nasdaq': 0.002, 'Dow': 0.004},
        'asian_markets_changes': {'Nikkei': 0.006, 'Hang Seng': 0.004},
        'usdinr_change': 0.002,
        'sector_strength': {'NIFTY ENERGY': 0.015, 'NIFTY IT': 0.01, 'NIFTY BANK': 0.005},
        'top_sectors': ['NIFTY ENERGY', 'NIFTY IT', 'NIFTY BANK']
    }

async def test_bot():
    ticks = mock_fetch_nifty100_realtime()
    global_ctx = mock_fetch_global_context()
    for symbol, tick in ticks.items():
        signal = {'side': 'buy', 'size': 0.5, 'confidence': 0.8, 'symbol': symbol}
        explanation = f"Mock trade for {symbol}"
        if allowed(signal, global_ctx):
            await send_alert(f"BUY Signal: {explanation}")
            print(f"Sent alert for {symbol}")
        else:
            print(f"Trade blocked for {symbol} due to risk checks")
    print("Testing force exit...")
    force_exit_positions()

if __name__ == "__main__":
    asyncio.run(test_bot())
