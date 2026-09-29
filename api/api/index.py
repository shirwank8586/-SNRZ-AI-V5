import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI, HTTPException
from market import candles
from snrz_engine import Candle, multi_timeframe

app = FastAPI(
    title="SNRZ AI V7",
    version="7.0"
)


@app.get("/")
def root():
    return {
        "ok": True,
        "engine": "SNRZ AI V7",
        "mode": "paper/educational",
        "method": "SNRZ-only",
        "status": "online"
    }


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "engine": "SNRZ AI V7",
        "mode": "paper/educational",
        "method": "SNRZ-only",
        "status": "online"
    }


@app.get("/api/multi-analysis")
async def multi_analysis():
    all_data = {}
    errors = {}

    timeframes = [
        "1mo",
        "1w",
        "1d",
        "4h",
        "1h",
        "30m",
        "15m",
        "5m",
        "1m"
    ]

    for tf in timeframes:
        try:
            raw = await candles(tf, 250)
            all_data[tf] = [Candle(**x) for x in raw]
        except Exception as e:
            errors[tf] = str(e)

    if not all_data:
        raise HTTPException(
            status_code=502,
            detail="No market data. Configure TWELVE_DATA_API_KEY on the backend."
        )

    result = multi_timeframe(all_data)

    result["engine"] = "SNRZ AI V7"
    result["mode"] = "paper/educational"
    result["method"] = "SNRZ-only"
    result["timeframes"] = timeframes
    result["errors"] = errors

    return result
