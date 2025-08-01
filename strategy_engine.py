from sklearn.preprocessing import StandardScaler
import numpy as np
import logging
import asyncio
from utils import send_alert

logging.basicConfig(level=logging.INFO, filename='logs/daily_log.csv', format='%(asctime)s,%(levelname)s,%(message)s')
scaler = StandardScaler()

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

def get_trade_features(tick, global_ctx):
    sector = SECTOR_MAPPING.get(tick['symbol'], 'Unknown')
    sector_strength = global_ctx['sector_strength'].get(sector, 0.0)

    features = [
        tick.get('ema_fast', 0.0),
        tick.get('ema_slow', 0.0),
        tick.get('macd', 0.0),
        tick.get('rsi', 0.0),
        tick.get('volume', 0.0),
        global_ctx.get('india_vix', 0.0),
        sector_strength,
        global_ctx.get('gift_nifty_change', 0.0),
        tick.get('atr', 0.0),
        global_ctx.get('usdinr_change', 0.0),
        sum(global_ctx['us_futures_changes'].values()) / len(global_ctx['us_futures_changes']),
        sum(global_ctx['asian_markets_changes'].values()) / len(global_ctx['asian_markets_changes'])
    ]
    if any(v is None for v in features):
        logging.error(f"Missing feature data for {tick['symbol']}")
        asyncio.run(send_alert(f"Missing feature data for {tick['symbol']}", error=True))
        raise ValueError("Incomplete feature data")
    try:
        normalized_features = scaler.fit_transform([features])[0]
        return normalized_features.tolist()
    except Exception as e:
        logging.error(f"Feature normalization failed for {tick['symbol']}: {e}")
        asyncio.run(send_alert(f"Feature normalization error for {tick['symbol']}: {e}", error=True))
        raise
