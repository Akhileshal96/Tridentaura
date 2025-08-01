from kiteconnect import KiteConnect
import logging
from dotenv import load_dotenv
import os

load_dotenv()
logging.basicConfig(level=logging.INFO, filename='logs/daily_log.csv', format='%(asctime)s,%(levelname)s,%(message)s')

kite = KiteConnect(api_key=os.getenv('KITE_API_KEY'))
kite.set_access_token(os.getenv('KITE_ACCESS_TOKEN'))
