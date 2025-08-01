import time
import logging
from concurrent.futures import ThreadPoolExecutor
from ai_trader.drl_agent import DRLTrader
from strategy_engine import get_trade_features
from risk_engine import allowed, force_exit_positions
from gpt_engine import approved as gpt_approved
from utils import log_trade, send_alert, explain_decision, start_telegram_bot
from global_context import fetch_global_context
from data_fetcher import fetch_nifty100_realtime
from kiteconnect import KiteConnect
from dotenv import load_dotenv
import asyncio
import threading
import os
import schedule

load_dotenv()
logging.basicConfig(level=logging.INFO, filename='logs/daily_log.csv', format='%(asctime)s,%(levelname)s,%(message)s')

drl_trader = DRLTrader(model_path='models/drl_legend.pt')
TICK_INTERVAL = 1
trading_live = True
kite = KiteConnect(api_key=os.getenv('KITE_API_KEY'))
kite.set_access_token(os.getenv('KITE_ACCESS_TOKEN'))

def execute_trade(signal):
    try:
        if signal['side'] == 'buy':
            kite.place_order(
                variety='regular',
                exchange='NSE',
                tradingsymbol=signal['symbol'],
                transaction_type='BUY',
                quantity=int(signal['size'] * 100),
                product='MIS',
                order_type='MARKET'
            )
        elif signal['side'] == 'sell':
            kite.place_order(
                variety='regular',
                exchange='NSE',
                tradingsymbol=signal['symbol'],
                transaction_type='SELL',
                quantity=int(signal['size'] * 100),
                product='MIS',
                order_type='MARKET'
            )
        logging.info(f"Executed {signal['side']} for {signal['symbol']}")
    except Exception as e:
        logging.error(f"Trade execution error: {e}")
        asyncio.run(send_alert(f"Trade execution error for {signal['symbol']}: {e}", error=True))

def process_stock(symbol, tick, global_ctx, drl_trader):
    try:
        features = get_trade_features(tick, global_ctx)
        signal = drl_trader.decide(features, symbol)
        explanation = explain_decision(signal, features)
        if allowed(signal, global_ctx) and asyncio.run(gpt_approved(signal, explanation)):
            execute_trade(signal)
            log_trade(signal, explanation)
            asyncio.run(send_alert(f"{signal['side'].upper()} Signal: {explanation}"))
    except Exception as e:
        logging.error(f"Error processing {symbol}: {e}")
        asyncio.run(send_alert(f"Error for {symbol}: {e}", error=True))

def main():
    threading.Thread(target=start_telegram_bot, daemon=True).start()
    schedule.every().day.at("15:15").do(force_exit_positions)

    with ThreadPoolExecutor(max_workers=3) as executor:
        while trading_live:
            try:
                ticks = fetch_nifty100_realtime()
                global_ctx = fetch_global_context()
                for symbol, tick in ticks.items():
                    executor.submit(process_stock, symbol, tick, global_ctx, drl_trader)
                schedule.run_pending()
            except Exception as e:
                logging.error(f"Multi-stock error: {e}")
                asyncio.run(send_alert(f"Multi-stock error: {e}", error=True))
            time.sleep(TICK_INTERVAL)

if __name__ == "__main__":
    main()
