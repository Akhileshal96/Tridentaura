from kiteconnect import KiteConnect
import logging
from dotenv import load_dotenv
import os
import webbrowser
import asyncio
from utils import send_alert

load_dotenv()
logging.basicConfig(level=logging.INFO, filename='logs/daily_log.csv', format='%(asctime)s,%(levelname)s,%(message)s')

def generate_new_access_token():
    api_key = os.getenv('KITE_API_KEY')
    api_secret = os.getenv('KITE_API_SECRET')
    kite = KiteConnect(api_key=api_key)

    login_url = f"https://kite.zerodha.com/connect/login?v=3&api_key={api_key}"
    print(f"Open this URL in your browser: {login_url}")
    webbrowser.open(login_url)

    try:
        request_token = input("Enter the request token from the URL: ")
        data = kite.generate_session(request_token, api_secret)
        access_token = data['access_token']
        with open('.env', 'r') as f:
            env_lines = f.readlines()
        with open('.env', 'w') as f:
            for line in env_lines:
                if line.startswith('KITE_ACCESS_TOKEN'):
                    f.write(f"KITE_ACCESS_TOKEN={access_token}\n")
                else:
                    f.write(line)
        logging.info("Access token updated successfully")
        print(f"Access token: {access_token}")
        return access_token
    except Exception as e:
        logging.error(f"Error generating access token: {e}")
        asyncio.run(send_alert(f"Error generating access token: {e}", error=True))
        raise

if __name__ == "__main__":
    generate_new_access_token()
