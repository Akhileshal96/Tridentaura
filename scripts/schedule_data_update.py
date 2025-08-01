import schedule
import time
from data_fetcher import fetch_nifty100_data
import logging
from utils import send_alert
import asyncio

logging.basicConfig(level=logging.INFO, filename='logs/daily_log.csv', format='%(asctime)s,%(levelname)s,%(message)s')

def update_nifty100_data():
    try:
        fetch_nifty100_data(save_to_csv=True)
        logging.info("Scheduled data update completed")
    except Exception as e:
        logging.error(f"Scheduled data update failed: {e}")
        asyncio.run(send_alert(f"Scheduled data update failed: {e}", error=True))

schedule.every().day.at("08:00").do(update_nifty100_data)

while True:
    schedule.run_pending()
    time.sleep(60)
