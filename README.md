# Trident Aura Bot

## Overview
Trading bot for NIFTY 100 stocks using Kite Connect, Telethon, xAI Grok/OpenAI, yfinance, and NSE API. Features buy/sell signals, global market context, risk control, and force exit at 3:15 PM IST.

## Features
- Buy/sell signals via DRL or RSI (buy < 30, sell > 70)
- Global context: GIFT Nifty, US futures, Asian markets, India VIX, USD/INR, NSE sectors
- Risk checks: confidence, trading hours, drawdown, position size
- Force exit at 3:15 PM IST
- Telegram commands: `/exclude`, `/include`, `/list_exclusions`
- Logging to `logs/daily_log.csv` and `logs/encrypted_log.csv`

## Setup
1. Clone repository:
   ```bash
   git clone https://github.com/your-username/trident_aura_bot.git
   cd trident_aura_bot
