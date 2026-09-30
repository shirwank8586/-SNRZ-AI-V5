from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Tuple

@dataclass
class Candle:
    time: Any
    open: float
    high: float
    low: float
    close: float

# SNRZ-only educational/paper analysis engine.

def bullish(c: Candle) -> bool:
    return c.close > c.open

def bearish(c: Candle) -> bool:
    return c.close < c.open

def body(c: Candle) -> float:
    return abs(c.close - c.open)

def candle_range(c: Candle) -> float:
    return max(c.high - c.low, 0.0)

def avg_range(data: List[Candle], n: int = 14) -> float:
    if not data:
        return 0.0
    xs = data[-n:]
    return sum(candle_range(x) for x in xs) / len(xs)

def zone_tolerance(data: List[Candle]) -> float:
    return max(avg_range(data) * 0.35, 1e-8)

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

    lower = min(c.open, c.close) - c.low
    upper = c.high - max(c.open, c.close)

    return (
        lower >= body(c) * 2
        and lower > upper
        and c.close >= c.low + r * 0.60
    )

def bearish_pin_bar(c: Candle) -> bool:
    r = candle_range(c)
    if r <= 0:
        return False

    upper = c.high - max(c.open, c.close)
    lower = min(c.open, c.close) - c.low

    return (
        upper >= body(c) * 2
        and upper > lower
        and c.close <= c.low + r * 0.40
    )

def confirmation(data: List[Candle]) -> Dict[str, bool]:
    if len(data) < 2:
        return {"bullish": False, "bearish": False}

    p, c = data[-2], data[-1]

    return {
        "bullish": (
            bullish_engulfing(p, c)
            or bullish_pin_bar(c)
        ),
        "bearish": (
            bearish_engulfing(p, c)
            or bearish_pin_bar(c)
        ),
    }

def market_structure(data: List[Candle]) -> str:
    if len(data) < 20:
        return "UNKNOWN"

    w = data[-20:]
    mid = len(w) // 2

    a, b = w[:mid], w[mid:]

    ah = max(x.high for x in a)
    al = min(x.low for x in a)

    bh = max(x.high for x in b)
    bl = min(x.low for x in b)

    if bh > ah and bl > al:
        return "UPTREND (HH/HL candidate)"

    if bh < ah and bl < al:
        return "DOWNTREND (LH/LL candidate)"

    return "SIDEWAYS"

def swing_levels(
    data: List[Candle],
    lookback: int = 2
) -> Tuple[List[float], List[float]]:

    highs, lows = [], []

    if len(data) < lookback * 2 + 3:
        return highs, lows

    for i in range(
        lookback,
        len(data) - lookback
    ):
        c = data[i]

        if c.high >= max(
            x.high
            for x in data[
                i-lookback:i+lookback+1
            ]
        ):
            highs.append(c.high)

        if c.low <= min(
            x.low
            for x in data[
                i-lookback:i+lookback+1
            ]
        ):
            lows.append(c.low)

    return highs, lows

def grouped_zones(
    data: List[Candle],
    kind: str,
    max_zones: int = 6
) -> List[Dict[str, Any]]:

    highs, lows = swing_levels(data)

    levels = highs if kind == "resistance" else lows

    if not levels:
        return []

    tol = zone_tolerance(data)
    clusters: List[List[float]] = []

    for level in levels:

        for cluster in clusters:

            if abs(
                level - sum(cluster) / len(cluster)
            ) <= tol:

                cluster.append(level)
                break

        else:
            clusters.append([level])

    clusters.sort(
        key=lambda c: len(c),
        reverse=True
    )

    zones = []

    for cluster in clusters[:max_zones]:

        center = sum(cluster) / len(cluster)

        touches = [
            i
            for i, c in enumerate(data)
            if (
                c.low <= center + tol
                and c.high >= center - tol
            )
        ]

        zones.append({
            "type": (
                "S"
                if kind == "support"
                else "R"
            ),
            "price": center,
            "tolerance": tol,
            "touches": len(touches),
            "reaction_indices": touches[-6:],
            "fresh": len(touches) <= 1,
        })

    return zones

def zone_state(
    data: List[Candle],
    zone: Dict[str, Any]
) -> Dict[str, Any]:

    z = zone["price"]
    tol = zone["tolerance"]
    kind = zone["type"]

    touches = []
    sweeps = 0
    closes_outside = 0
    closes_back_inside = 0

    for i, c in enumerate(data):

        if (
            c.low <= z + tol
            and c.high >= z - tol
        ):
            touches.append(i)

        if kind == "S":

            if (
                c.low < z - tol
                and c.close >= z - tol
            ):
                sweeps += 1

            if c.close < z - tol:
                closes_outside += 1

            if (
                c.close >= z - tol
                and c.low < z - tol
            ):
                closes_back_inside += 1

        else:

            if (
                c.high > z + tol
                and c.close <= z + tol
            ):
                sweeps += 1

            if c.close > z + tol:
                closes_outside += 1

            if (
                c.close <= z + tol
                and c.high > z + tol
            ):
                closes_back_inside += 1

    return {
        "touches": len(touches),
        "sweeps": sweeps,
        "closes_outside": closes_outside,
        "closes_back_inside": closes_back_inside,
        "po2": len(touches) >= 2,
        "fresh": len(touches) <= 1,
    }

def detect_sbr_rbs(
    data: List[Candle],
    zone: Dict[str, Any]
) -> Optional[str]:

    z = zone["price"]
    tol = zone["tolerance"]
    kind = zone["type"]

    for i in range(1, len(data)):

        p, c = data[i-1], data[i]

        if (
            kind == "S"
            and p.close >= z - tol
            and c.close < z - tol
        ):
            return "SBR"

        if (
            kind == "R"
            and p.close <= z + tol
            and c.close > z + tol
        ):
            return "RBS"

    return None

def detect_srr_rss(
    data: List[Candle],
    zone: Dict[str, Any]
) -> Optional[str]:

    z = zone["price"]
    tol = zone["tolerance"]
    kind = zone["type"]

    breaks = 0

    for i in range(1, len(data)):

        p, c = data[i-1], data[i]

        if (
            kind == "S"
            and p.close >= z - tol
            and c.close < z - tol
        ):
            breaks += 1

        if (
            kind == "R"
            and p.close <= z + tol
            and c.close > z + tol
        ):
            breaks += 1

    if breaks >= 2:
        return (
            "SRR"
            if kind == "S"
            else "RSS"
        )

    return None

def liquidity_events(
    data: List[Candle]
) -> Dict[str, bool]:

    if len(data) < 13:
        return {
            "bullish_sweep": False,
            "bearish_sweep": False,
            "bullish_run": False,
            "bearish_run": False,
        }

    cur = data[-1]

    prior_low = min(
        x.low for x in data[-12:-1]
    )

    prior_high = max(
        x.high for x in data[-12:-1]
    )

    return {
        "bullish_sweep": (
            cur.low < prior_low
            and cur.close > prior_low
        ),

        "bearish_sweep": (
            cur.high > prior_high
            and cur.close < prior_high
        ),

        "bullish_run": (
            cur.close > prior_high
        ),

        "bearish_run": (
            cur.close < prior_low
        ),
    }

def best_zone(
    data: List[Candle],
    kind: str
) -> Optional[Dict[str, Any]]:

    zones = grouped_zones(data, kind)

    if not zones:
        return None

    cur = data[-1].close

    return min(
        zones,
        key=lambda z: abs(
            z["price"] - cur
        )
    )

def analyze_snrz(
    data: List[Candle]
) -> Dict[str, Any]:

    if len(data) < 20:
        return {
            "signal": "WAIT",
            "reason": "Not enough candles",
            "structure": "UNKNOWN",
        }

    cur = data[-1]

    structure = market_structure(data)
    conf = confirmation(data)
    liq = liquidity_events(data)

    support = best_zone(
        data,
        "support"
    )

    resistance = best_zone(
        data,
        "resistance"
    )

    zones = []
    buy = []
    sell = []

    for zone in (
        support,
        resistance
    ):

        if not zone:
            continue

        state = zone_state(
            data,
            zone
        )

        transition = detect_sbr_rbs(
            data,
            zone
        )

        multi_break = detect_srr_rss(
            data,
            zone
        )

        z = dict(zone)
        z.update(state)

        if transition:

            z["transition"] = transition

            z["inversion"] = (
                "I-VS candidate"
                if transition == "RBS"
                else "I-VR candidate"
            )

        if multi_break:
            z["multi_break"] = multi_break

        zones.append(z)

        if (
            zone["type"] == "S"
            and state["po2"]
        ):
            buy.append("PO2 / Support")

        if (
            zone["type"] == "R"
            and state["po2"]
        ):
            sell.append("PO2 / Resistance")

        if transition == "RBS":
            buy.append("RBS")

        if transition == "SBR":
            sell.append("SBR")

        if multi_break == "SRR":
            buy.append("SRR")

        if multi_break == "RSS":
            sell.append("RSS")

    if (
        support
        and zone_state(
            data,
            support
        )["touches"] >= 2
    ):

        if conf["bullish"]:
            buy.append(
                "V.S candidate"
            )

        if liq["bullish_sweep"]:
            buy.append(
                "V.S + Liquidity Sweep"
            )

    if (
        resistance
        and zone_state(
            data,
            resistance
        )["touches"] >= 2
    ):

        if conf["bearish"]:
            sell.append(
                "V.R candidate"
            )

        if liq["bearish_sweep"]:
            sell.append(
                "V.R + Liquidity Sweep"
            )

    if liq["bullish_sweep"]:
        buy.append("Liquidity Sweep")

    if liq["bearish_sweep"]:
        sell.append("Liquidity Sweep")

    if liq["bullish_run"]:
        buy.append("Liquidity Run")

    if liq["bearish_run"]:
        sell.append("Liquidity Run")

    if structure.startswith("UPTREND"):
        buy.append(
            "Market Structure HH/HL"
        )

    if structure.startswith("DOWNTREND"):
        sell.append(
            "Market Structure LH/LL"
        )

    buy = list(dict.fromkeys(buy))
    sell = list(dict.fromkeys(sell))

    signal = "WAIT"
    reason: Any = {
        "buy": buy,
        "sell": sell
    }

    if (
        structure.startswith("UPTREND")
        and conf["bullish"]
        and buy
    ):

        signal = "BUY_CANDIDATE"
        reason = buy

    elif (
        structure.startswith("DOWNTREND")
        and conf["bearish"]
        and sell
    ):

        signal = "SELL_CANDIDATE"
        reason = sell

    return {
        "signal": signal,
        "reason": reason,
        "structure": structure,
        "price": cur.close,

        "sl_reference": (
            cur.low
            if signal == "BUY_CANDIDATE"
            else cur.high
            if signal == "SELL_CANDIDATE"
            else None
        ),

        "confirmation": conf,
        "liquidity": liq,
        "zones": zones,

        "snrz": {
            "VS": (
                "candidate"
                if "V.S candidate" in buy
                else False
            ),

            "VR": (
                "candidate"
                if "V.R candidate" in sell
                else False
            ),

            "PO2": any(
                z.get("po2")
                for z in zones
            ),

            "RBS": "RBS" in buy,
            "SBR": "SBR" in sell,
            "SRR": "SRR" in buy,
            "RSS": "RSS" in sell,

            "LiquiditySweep": (
                liq["bullish_sweep"]
                or liq["bearish_sweep"]
            ),

            "LiquidityRun": (
                liq["bullish_run"]
                or liq["bearish_run"]
            ),
        },
    }

def detect_signal(
    data: List[Candle]
) -> Dict[str, Any]:
    return analyze_snrz(data)

def multi_timeframe(
    all_data: Dict[str, List[Candle]]
) -> Dict[str, Any]:

    return {
        "engine": "SNRZ AI V7",
        "method": "SNRZ-only",
        "mode": "paper/educational",

        "analysis": {
            tf: analyze_snrz(data)
            for tf, data in all_data.items()
        },
    }
