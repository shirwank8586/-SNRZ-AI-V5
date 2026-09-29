import os
import httpx
from dotenv import load_dotenv

load_dotenv()

API = "https://api.twelvedata.com/time_series"

TF_MAP = {
    "1m": "1min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "1h",
    "4h": "4h",
    "1d": "1day",
    "1w": "1week",
    "1mo": "1month"
}


async def candles(interval="15m", outputsize=250):
    key = os.getenv("TWELVE_DATA_API_KEY", "").strip()
    symbol = os.getenv("SYMBOL", "XAU/USD")

    if not key:
        raise RuntimeError(
            "TWELVE_DATA_API_KEY is not configured"
        )

    params = {
        "symbol": symbol,
        "interval": TF_MAP.get(interval, interval),
        "outputsize": outputsize,
        "apikey": key,
        "order": "ASC"
    }

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(API, params=params)
        response.raise_for_status()
        data = response.json()

    if "values" not in data:
        raise RuntimeError(
            data.get("message", "Market data error")
        )

    return [
        {
            "time": v["datetime"],
            "open": float(v["open"]),
            "high": float(v["high"]),
            "low": float(v["low"]),
            "close": float(v["close"])
        }
        for v in data["values"]
    ]
