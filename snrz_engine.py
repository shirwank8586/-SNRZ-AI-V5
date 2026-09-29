from dataclasses import dataclass
from typing import Dict, List, Any


@dataclass
class Candle:
    time: Any
    open: float
    high: float
    low: float
    close: float


def bullish(c: Candle) -> bool:
    return c.close > c.open


def bearish(c: Candle) -> bool:
    return c.close < c.open


def body(c: Candle) -> float:
    return abs(c.close - c.open)


def candle_range(c: Candle) -> float:
    return c.high - c.low


def bullish_engulfing(prev: Candle, cur: Candle) -> bool:
    return (
        bearish(prev)
        and bullish(cur)
        and cur.open <= prev.close
        and cur.close >= prev.open
    )


def bearish_engulfing(prev: Candle, cur: Candle) -> bool:
    return (
        bullish(prev)
        and bearish(cur)
        and cur.open >= prev.close
        and cur.close <= prev.open
    )


def bullish_pin_bar(c: Candle) -> bool:
    r = candle_range(c)
    if r <= 0:
        return False

    lower_wick = min(c.open, c.close) - c.low
    upper_wick = c.high - max(c.open, c.close)

    return (
        lower_wick >= body(c) * 2
        and lower_wick > upper_wick
        and c.close >= c.low + r * 0.6
    )


def bearish_pin_bar(c: Candle) -> bool:
    r = candle_range(c)
    if r <= 0:
        return False

    upper_wick = c.high - max(c.open, c.close)
    lower_wick = min(c.open, c.close) - c.low

    return (
        upper_wick >= body(c) * 2
        and upper_wick > lower_wick
        and c.close <= c.low + r * 0.4
    )


def market_structure(data: List[Candle]) -> str:
    if len(data) < 10:
        return "UNKNOWN"

    highs = [x.high for x in data[-10:]]
    lows = [x.low for x in data[-10:]]

    if highs[-1] > highs[0] and lows[-1] > lows[0]:
        return "UPTREND"

    if highs[-1] < highs[0] and lows[-1] < lows[0]:
        return "DOWNTREND"

    return "SIDEWAYS"


def liquidity_sweep(data: List[Candle]) -> Dict[str, bool]:
    if len(data) < 3:
        return {"bullish": False, "bearish": False}

    prev = data[-2]
    cur = data[-1]

    previous_low = min(x.low for x in data[-12:-2])
    previous_high = max(x.high for x in data[-12:-2])

    bullish_sweep = (
        cur.low < previous_low
        and cur.close > previous_low
    )

    bearish_sweep = (
        cur.high > previous_high
        and cur.close < previous_high
    )

    return {
        "bullish": bullish_sweep,
        "bearish": bearish_sweep
    }


def detect_signal(data: List[Candle]) -> Dict[str, Any]:
    if len(data) < 20:
        return {
            "signal": "WAIT",
            "reason": "Not enough candles",
            "structure": "UNKNOWN"
        }

    cur = data[-1]
    prev = data[-2]

    structure = market_structure(data)
    sweep = liquidity_sweep(data)

    bull_confirm = (
        bullish_engulfing(prev, cur)
        or bullish_pin_bar(cur)
    )

    bear_confirm = (
        bearish_engulfing(prev, cur)
        or bearish_pin_bar(cur)
    )

    buy_reasons = []
    sell_reasons = []

    # SNRZ confirmation concepts
    if structure == "UPTREND":
        buy_reasons.append("Market Structure HH/HL candidate")

    if structure == "DOWNTREND":
        sell_reasons.append("Market Structure LH/LL candidate")

    if sweep["bullish"]:
        buy_reasons.append("Liquidity Sweep")

    if sweep["bearish"]:
        sell_reasons.append("Liquidity Sweep")

    if bull_confirm:
        buy_reasons.append("Bullish confirmation")

    if bear_confirm:
        sell_reasons.append("Bearish confirmation")

    # SNRZ directional framework:
    # BUY: VS / IVR / RBS / SRR
    # SELL: VR / IVS / SBR / RSS
    if (
        structure == "UPTREND"
        and (sweep["bullish"] or bull_confirm)
    ):
        return {
            "signal": "BUY_CANDIDATE",
            "reason": buy_reasons,
            "structure": structure,
            "price": cur.close,
            "sl_reference": cur.low
        }

    if (
        structure == "DOWNTREND"
        and (sweep["bearish"] or bear_confirm)
    ):
        return {
            "signal": "SELL_CANDIDATE",
            "reason": sell_reasons,
            "structure": structure,
            "price": cur.close,
            "sl_reference": cur.high
        }

    return {
        "signal": "WAIT",
        "reason": {
            "buy": buy_reasons,
            "sell": sell_reasons
        },
        "structure": structure,
        "price": cur.close
    }


def multi_timeframe(
    all_data: Dict[str, List[Candle]]
) -> Dict[str, Any]:

    analysis = {}

    for timeframe, data in all_data.items():
        analysis[timeframe] = detect_signal(data)

    return {
        "engine": "SNRZ AI V7",
        "method": "SNRZ-only",
        "mode": "paper/educational",
        "analysis": analysis
    }
