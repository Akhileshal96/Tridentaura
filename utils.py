from cryptography.fernet import Fernet
import os
import json
import logging
from telethon import TelegramClient, events
from data_fetcher import get_nifty100_symbols
from dotenv import load_dotenv
import threading
import asyncio
from kite_api_config import kite

load_dotenv()
logging.basicConfig(level=logging.INFO, filename='logs/daily_log.csv', format='%(asctime)s,%(levelname)s,%(message)s')

key_file = 'logs/encryption_key.key'
if os.path.exists(key_file):
    with open(key_file, 'rb') as f:
        key = f.read()
else:
    os.makedirs('logs', exist_ok=True)
    key = Fernet.generate_key()
    with open(key_file, 'wb') as f:
        f.write(key)
cipher = Fernet(key)

excluded_stocks_lock = threading.Lock()
excluded_stocks = set()

EXCLUDED_STOCKS_FILE = 'data/excluded_stocks.json'
def load_excluded_stocks():
    with excluded_stocks_lock:
        try:
            if os.path.exists(EXCLUDED_STOCKS_FILE):
                with open(EXCLUDED_STOCKS_FILE, 'rb') as f:
                    encrypted_data = f.read()
                decrypted_data = cipher.decrypt(encrypted_data).decode()
                data = json.loads(decrypted_data)
                return set(data.get('excluded_stocks', []))
            return set()
        except Exception as e:
            logging.error(f"Error loading excluded stocks: {e}")
            asyncio.run(send_alert(f"Error loading excluded stocks: {e}", error=True))
            return set()

def save_excluded_stocks(excluded_stocks):
    with excluded_stocks_lock:
        try:
            os.makedirs('data', exist_ok=True)
            data = {"excluded_stocks": list(excluded_stocks)}
            encrypted_data = cipher.encrypt(json.dumps(data).encode())
            with open(EXCLUDED_STOCKS_FILE, 'wb') as f:
                f.write(encrypted_data)
            logging.info("Updated excluded stocks")
        except Exception as e:
            logging.error(f"Error saving excluded stocks: {e}")
            asyncio.run(send_alert(f"Error saving excluded stocks: {e}", error=True))

excluded_stocks = load_excluded_stocks()

TELEGRAM_API_ID = os.getenv('TELEGRAM_API_ID')
TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
client = TelegramClient('bot', TELEGRAM_API_ID, TELEGRAM_API_HASH).start(bot_token=TELEGRAM_TOKEN)

@client.on(events.NewMessage(pattern='/exclude'))
async def exclude_command(event):
    try:
        stocks = event.message.text.split()[1].upper().split(',') if len(event.message.text.split()) > 1 else []
        valid_symbols = get_nifty100_symbols()
        invalid_stocks = [s for s in stocks if s not in valid_symbols]
        if invalid_stocks:
            await event.reply(f"Invalid stocks (not in NIFTY 100): {', '.join(invalid_stocks)}")
            return
        with excluded_stocks_lock:
            global excluded_stocks
            excluded_stocks.update(stocks)
            save_excluded_stocks(excluded_stocks)
        logging.info(f"Excluded stocks: {stocks} by user {event.sender_id}")
        await event.reply(f"Excluded stocks: {', '.join(stocks)}")
    except Exception as e:
        logging.error(f"Error in exclude command: {e}")
        await send_alert(f"Error in exclude command: {e}", error=True)
        await event.reply("Error processing /exclude command")

@client.on(events.NewMessage(pattern='/include'))
async def include_command(event):
    try:
        stocks = event.message.text.split()[1].upper().split(',') if len(event.message.text.split()) > 1 else []
        with excluded_stocks_lock:
            global excluded_stocks
            removed = [s for s in stocks if s in excluded_stocks]
            excluded_stocks.difference_update(stocks)
            save_excluded_stocks(excluded_stocks)
        logging.info(f"Removed from exclusions: {removed} by user {event.sender_id}")
        await event.reply(f"Removed from exclusions: {', '.join(removed)}")
    except Exception as e:
        logging.error(f"Error in include command: {e}")
        await send_alert(f"Error in include command: {e}", error=True)
        await event.reply("Error processing /include command")

@client.on(events.NewMessage(pattern='/list_exclusions'))
async def list_exclusions_command(event):
    try:
        with excluded_stocks_lock:
            if excluded_stocks:
                await event.reply(f"Excluded stocks: {', '.join(sorted(excluded_stocks))}")
            else:
                await event.reply("No stocks excluded")
    except Exception as e:
        logging.error(f"Error in list_exclusions command: {e}")
        await send_alert(f"Error in list_exclusions command: {e}", error=True)
        await event.reply("Error processing /list_exclusions command")

def start_telegram_bot():
    try:
        client.run_until_disconnected()
    except Exception as e:
        logging.error(f"Telegram bot error: {e}")
        asyncio.run(send_alert(f"Telegram bot error: {e}", error=True))

def get_portfolio_pnl():
    try:
        positions = kite.positions()
        return sum(pos['pnl'] for pos in positions['day'])
    except Exception as e:
        logging.error(f"Error calculating P&L: {e}")
        asyncio.run(send_alert(f"Error calculating P&L: {e}", error=True))
        return 0.0

def explain_decision(signal, features):
    rsi, macd, vix = features[3], features[2], features[5]
    portfolio_pnl = get_portfolio_pnl()
    if signal['side'] == 'buy':
        return (f"AI BUY: {signal['confidence']:.2f} | RSI: {rsi:.1f}, MACD: {macd:.2f}, "
                f"VIX: {vix:.1f}, P&L: {portfolio_pnl:.2f}")
    elif signal['side'] == 'sell':
        return (f"AI SELL: {signal['confidence']:.2f} | RSI: {rsi:.1f}, MACD: {macd:.2f}, "
                f"VIX: {vix:.1f}, P&L: {portfolio_pnl:.2f}")
    return f"AI HOLD: No edge | RSI: {rsi:.1f}, P&L: {portfolio_pnl:.2f}"

def encrypt_log(data, filename='logs/encrypted_log.csv'):
    try:
        encrypted = cipher.encrypt(data.encode())
        with open(filename, 'wb') as f:
            f.write(encrypted)
    except Exception as e:
        logging.error(f"Error encrypting log: {e}")
        asyncio.run(send_alert(f"Error encrypting log: {e}", error=True))

def log_trade(signal, explanation):
    data = f"{signal},{explanation}\n"
    encrypt_log(data)
    logging.info(f"Trade logged: {signal['side']}, {explanation}")

async def send_alert(message, error=False):
    try:
        chat_id = os.getenv('TELEGRAM_CHAT_ID')
        prefix = "Error Alert: " if error else ""
        await client.send_message(chat_id, f"{prefix}{message}")
    except Exception as e:
        logging.error(f"Error sending Telegram alert: {e}")
