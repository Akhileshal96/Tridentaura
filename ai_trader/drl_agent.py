import torch
import numpy as np
import logging
from utils import send_alert
import asyncio

logging.basicConfig(level=logging.INFO, filename='logs/daily_log.csv', format='%(asctime)s,%(levelname)s,%(message)s')

class DRLTrader:
    def __init__(self, model_path='models/drl_legend.pt', fallback_strategy='rule_based'):
        self.model = None
        self.fallback_strategy = fallback_strategy
        try:
            self.model = torch.load(model_path, map_location='cpu')
            self.model.eval()
            logging.info(f"Loaded DRL model from {model_path}")
        except FileNotFoundError:
            logging.error(f"Model {model_path} not found. Using {fallback_strategy}.")
            asyncio.run(send_alert(f"Model {model_path} not found. Using {fallback_strategy}.", error=True))
        except Exception as e:
            logging.error(f"Error loading model: {e}. Using {fallback_strategy}.")
            asyncio.run(send_alert(f"Error loading model: {e}. Using {fallback_strategy}.", error=True))

    def decide(self, features, symbol):
        if self.model:
            try:
                obs = torch.tensor(features, dtype=torch.float32).unsqueeze(0)
                with torch.no_grad():
                    output = self.model(obs)
                action = int(torch.argmax(output).item())
                side = {0: 'hold', 1: 'buy', 2: 'sell'}[action]
                confidence = float(torch.softmax(output, dim=1).max().item())
                size = min(1.0, confidence)
            except Exception as e:
                logging.error(f"DRL inference error: {e}. Using fallback.")
                asyncio.run(send_alert(f"DRL inference error for {symbol}: {e}. Using fallback.", error=True))
                side, confidence, size = self._rule_based_decision(features)
        else:
            side, confidence, size = self._rule_based_decision(features)
        return {"side": side, "size": size, "confidence": confidence, "symbol": symbol}

    def _rule_based_decision(self, features):
        rsi = features[3]
        if rsi > 70:
            return 'sell', 0.7, 0.5
        elif rsi < 30:
            return 'buy', 0.7, 0.5
        return 'hold', 0.5, 0.0
