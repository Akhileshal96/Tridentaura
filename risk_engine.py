import yaml
from datetime import datetime, time
import logging
from kiteconnect import KiteConnect
from dotenv import load_dotenv
import os
import asyncio
from data_fetcher import get_nifty100_symbols
from utils import send_alert

load_dotenv()
logging.basicConfig(level=logging.INFO, filename='logs/daily_log.csv', format='%(asctime)s,%(levelname)s,%(message)s')

kite = KiteConnect(api_key=os.getenv('KITE_API_KEY'))
kite.set_access_token(os.getenv('KITE_ACCESS_TOKEN'))

with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

SECTOR_MAPPING = {
    'RELIANCE': 'NIFTY ENERGY',
    'TCS': 'NIFTY IT',
    'HDFCBANK': 'NIFTY BANK',
    'INFY': 'NIFTY IT',
    'HINDUNILVR': 'NIFTY FMCG',
    'ICICIBANK': 'NIFTY BANK',
    'SBIN': 'NIFTY BANK'
    # Update with actual NSE sector assignments
}

def allowed(signal, global_ctx):
    try:
        if signal["confidence"] < config['risk']['confidence_threshold']:
            return False
        now = datetime.now().time()
        start = time(*map(int, config['risk']['trading_hours']['start'].split(':')))
        end = time(*map(int, config['risk']['trading_hours']['end'].split(':')))
        if not (start <= now <= end):
            logging.info("Outside trading hours")
            return False
        if portfolio_drawdown() > config['risk']['max_drawdown']:
            logging.warning("Max drawdown exceeded")
            return False
        if get_position_size(signal['symbol']) > config['risk']['max_position_size']:
            logging.warning(f"Position limit exceeded for {signal['symbol']}")
            return False
        if global_ctx['india_vix'] > config['risk']['global_context']['vix_threshold']:
            logging.warning(f"India VIX too high: {global_ctx['india_vix']}")
            return False
        if global_ctx['gift_nifty_change'] < -config['risk']['global_context']['gift_nifty_gap']:
            logging.warning(f"GIFT Nifty gap down: {global_ctx['gift_nifty_change']:.2%}")
            return False
        for name, change in global_ctx['us_futures_changes'].items():
            if change < -config['risk']['global_context']['us_futures_gap']:
                logging.warning(f"{name} futures gap down: {change:.2%}")
                return False
        for name, change in global_ctx['asian_markets_changes'].items():
            if change < -config['risk']['global_context']['asian_markets_gap']:
                logging.warning(f"{name} market gap down: {change:.2%}")
                return False
        if global_ctx['usdinr_change'] > config['risk']['global_context']['usdinr_change']:
            logging.warning(f"USD/INR change too high: {global_ctx['usdinr_change']:.2%}")
            return False
        symbol = signal['symbol']
        if symbol not in SECTOR_MAPPING:
            logging.warning(f"No sector mapping for {symbol}")
            return False
        sector = SECTOR_MAPPING[symbol]
        if sector not in global_ctx['top_sectors']:
            logging.warning(f"{symbol} not in top sectors: {global_ctx['top_sectors']}")
            return False
        return True
    except Exception as e:
        logging.error(f"Risk check error: {e}")
        asyncio.run(send_alert(f"Risk check error: {e}", error=True))
        return False

def portfolio_drawdown():
    try:
        positions = kite.positions()
        total_pnl = sum(pos['pnl'] for pos in positions['day'])
        historical_high = 1000000  # Replace with your portfolio's historical high
        return max(0, (historical_high - total_pnl) / historical_high)
    except Exception as e:
        logging.error(f"Portfolio drawdown calculation error: {e}")
        asyncio.run(send_alert(f"Portfolio drawdown calculation error: {e}", error=True))
        return 0.0

def get_position_size(symbol):
    try:
        positions = kite.positions()
        return sum(pos['quantity'] for pos in positions['day'] if pos['tradingsymbol'] == symbol)
    except Exception as e:
        logging.error(f"Position size calculation error for {symbol}: {e}")
        asyncio.run(send_alert(f"Position size calculation error for {symbol}: {e}", error=True))
        return 0

def force_exit_positions():
    try:
        positions = kite.positions()
        open_positions = [pos for pos in positions['day'] if pos['quantity'] != 0]
        for pos in open_positions:
            symbol = pos['tradingsymbol']
            quantity = abs(pos['quantity'])
            transaction_type = 'SELL' if pos['quantity'] > 0 else 'BUY'
            kite.place_order(
                variety='regular',
                exchange='NSE',
                tradingsymbol=symbol,
                transaction_type=transaction_type,
                quantity=quantity,
                product='MIS',
                order_type='MARKET'
            )
            logging.info(f"Force exited {transaction_type} for {symbol}, quantity: {quantity}")
            asyncio.run(send_alert(f"Force exited {transaction_type} for {symbol}, quantity: {quantity}"))
        if not open_positions:
            logging.info("No open positions to force exit")
            asyncio.run(send_alert("No open positions to force exit at 15:15 IST"))
    except Exception as e:
        logging.error(f"Force exit error: {e}")
        asyncio.run(send_alert(f"Force exit error: {e}", error=True))
