import asyncio
import logging
import requests
import os
from dotenv import load_dotenv
import json
from utils import send_alert

load_dotenv()
logging.basicConfig(level=logging.INFO, filename='logs/daily_log.csv', format='%(asctime)s,%(levelname)s,%(message)s')

async def approved(signal, explanation):
    provider = os.getenv('GPT_API_PROVIDER', 'xai').lower()
    try:
        if signal['confidence'] >= 0.7 and os.getenv('XAI_API_KEY'):
            gpt_response = await call_xai_api(signal, explanation)
            provider = 'xai'
        elif os.getenv('OPENAI_API_KEY'):
            gpt_response = await call_openai_api(signal, explanation)
            provider = 'openai'
        else:
            raise ValueError("No API key available")
        if gpt_response['approved']:
            return True
        logging.info(f"GPT ({provider}) vetoed trade: {gpt_response['reason']}")
        return False
    except Exception as e:
        logging.error(f"GPT approval error ({provider}): {e}")
        asyncio.run(send_alert(f"GPT approval error ({provider}): {e}", error=True))
        gpt_response = await mock_gpt_api(signal, explanation)
        logging.warning("Using mock GPT API as fallback")
        return gpt_response['approved']

async def call_openai_api(signal, explanation):
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set in .env")
    try:
        prompt = (
            f"Review the following trade signal and explanation:\n"
            f"Signal: {signal['side']} (Confidence: {signal['confidence']:.2f}, Size: {signal['size']:.2f})\n"
            f"Explanation: {explanation}\n"
            f"Is this trade reasonable based on the signal and market conditions? "
            f"Return a JSON object with 'approved' (boolean) and 'reason' (string)."
        )
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 200,
            "temperature": 0.7
        }
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        result = response.json()
        response_text = result['choices'][0]['message']['content']
        try:
            gpt_response = json.loads(response_text)
            if not isinstance(gpt_response, dict) or 'approved' not in gpt_response or 'reason' not in gpt_response:
                raise ValueError("Invalid OpenAI response format")
            return gpt_response
        except json.JSONDecodeError:
            if "approve" in response_text.lower():
                return {'approved': True, 'reason': 'Trade approved by OpenAI'}
            return {'approved': False, 'reason': 'Invalid OpenAI response format'}
    except Exception as e:
        logging.error(f"OpenAI API call failed: {e}")
        asyncio.run(send_alert(f"OpenAI API call failed: {e}", error=True))
        raise

async def call_xai_api(signal, explanation):
    api_key = os.getenv('XAI_API_KEY')
    if not api_key:
        raise ValueError("XAI_API_KEY not set in .env")
    try:
        prompt = (
            f"Review the following trade signal and explanation:\n"
            f"Signal: {signal['side']} (Confidence: {signal['confidence']:.2f}, Size: {signal['size']:.2f})\n"
            f"Explanation: {explanation}\n"
            f"Is this trade reasonable based on the signal and market conditions? "
            f"Return a JSON object with 'approved' (boolean) and 'reason' (string)."
        )
        url = "https://api.x.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "grok-3",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 200,
            "temperature": 0.7
        }
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        result = response.json()
        response_text = result['choices'][0]['message']['content']
        try:
            gpt_response = json.loads(response_text)
            if not isinstance(gpt_response, dict) or 'approved' not in gpt_response or 'reason' not in gpt_response:
                raise ValueError("Invalid xAI response format")
            return gpt_response
        except json.JSONDecodeError:
            if "approve" in response_text.lower():
                return {'approved': True, 'reason': 'Trade approved by Grok'}
            return {'approved': False, 'reason': 'Invalid xAI response format'}
    except Exception as e:
        logging.error(f"xAI API call failed: {e}")
        asyncio.run(send_alert(f"xAI API call failed: {e}", error=True))
        raise

async def mock_gpt_api(signal, explanation):
    if signal['confidence'] < 0.6 or "weak" in explanation.lower():
        return {'approved': False, 'reason': 'Low confidence or weak signal'}
    return {'approved': True, 'reason': 'Trade aligns with strategy'}
