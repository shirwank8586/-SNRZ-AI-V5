from dataclasses import dataclass
from typing import Any, Dict, List

@dataclass
class Candle:
    time: Any
    open: float
    high: float
    low: float
    close: float

def bullish(c): return c.close > c.open
def bearish(c): return c.close < c.open
def body(c): return abs(c.close-c.open)
def rng(c): return max(c.high-c.low,0.0)

def avg_range(d,n=14):
    x=d[-n:]
    return sum(rng(c) for c in x)/len(x) if x else 0.0

def tolerance(d):
    return max(avg_range(d)*0.35,1e-8)

def bull_engulf(p,c):
    return bearish(p) and bullish(c) and c.open<=p.close and c.close>=p.open

def bear_engulf(p,c):
    return bullish(p) and bearish(c) and c.open>=p.close and c.close<=p.open

def bull_pin(c):
    r=rng(c)
    if not r:return False
    lw=min(c.open,c.close)-c.low
    uw=c.high-max(c.open,c.close)
    return lw>=body(c)*2 and lw>uw and c.close>=c.low+r*.60

def bear_pin(c):
    r=rng(c)
    if not r:return False
    uw=c.high-max(c.open,c.close)
    lw=min(c.open,c.close)-c.low
    return uw>=body(c)*2 and uw>lw and c.close<=c.low+r*.40

def market_structure(d):
    if len(d)<20:
        return "UNKNOWN"

    a,b=d[-20:-10],d[-10:]

    ah,al=max(x.high for x in a),min(x.low for x in a)
    bh,bl=max(x.high for x in b),min(x.low for x in b)

    if bh>ah and bl>al:
        return "UPTREND (HH/HL candidate)"

    if bh<ah and bl<al:
        return "DOWNTREND (LH/LL candidate)"

    return "SIDEWAYS"

def liquidity(d):
    if len(d)<13:
        return {
            "bullish_sweep":False,
            "bearish_sweep":False,
            "bullish_run":False,
            "bearish_run":False
        }

    c=d[-1]
    lo=min(x.low for x in d[-12:-1])
    hi=max(x.high for x in d[-12:-1])

    return {
        "bullish_sweep":c.low<lo and c.close>lo,
        "bearish_sweep":c.high>hi and c.close<hi,
        "bullish_run":c.close>hi,
        "bearish_run":c.close<lo
    }

def swings(d,n=2):
    hs,ls=[],[]

    for i in range(n,len(d)-n):
        w=d[i-n:i+n+1]
        c=d[i]

        if c.high>=max(x.high for x in w):
            hs.append(c.high)

        if c.low<=min(x.low for x in w):
            ls.append(c.low)

    return hs,ls

def zones(d,kind):
    hs,ls=swings(d)
    levels=hs if kind=="R" else ls

    if not levels:
        return []

    t=tolerance(d)
    clusters=[]

    for x in levels:
        for cl in clusters:
            if abs(x-sum(cl)/len(cl))<=t:
                cl.append(x)
                break
        else:
            clusters.append([x])

    clusters.sort(key=len,reverse=True)

    out=[]

    for cl in clusters[:6]:
        p=sum(cl)/len(cl)

        touches=sum(
            1 for c in d
            if c.low<=p+t and c.high>=p-t
        )

        out.append({
            "type":kind,
            "price":p,
            "tolerance":t,
            "touches":touches,
            "fresh":touches<=1
        })

    return out

def nearest(d,kind):
    z=zones(d,kind)

    return min(
        z,
        key=lambda x:abs(x["price"]-d[-1].close)
    ) if z else None

def zone_touch(d,z):
    if not z:
        return False

    p,t=z["price"],z["tolerance"]
    c=d[-1]

    return c.low<=p+t and c.high>=p-t

def transitions(d,z):
    if not z:
        return []

    p,t,k=z["price"],z["tolerance"],z["type"]
    out=[]

    for a,b in zip(d[:-1],d[1:]):

        if k=="S" and a.close>=p-t and b.close<p-t:
            out.append("SBR")

        if k=="R" and a.close<=p+t and b.close>p+t:
            out.append("RBS")

    return list(dict.fromkeys(out))

def zone_features(d,z):
    if not z:
        return {}

    p,t,k=z["price"],z["tolerance"],z["type"]

    touches=0
    sweeps=0
    outside=0

    for c in d:

        if c.low<=p+t and c.high>=p-t:
            touches+=1

        if k=="S":

            if c.low<p-t and c.close>=p-t:
                sweeps+=1

            if c.close<p-t:
                outside+=1

        else:

            if c.high>p+t and c.close<=p+t:
                sweeps+=1

            if c.close>p+t:
                outside+=1

    return {
        "touches":touches,
        "po2":touches>=2,
        "fresh":touches<=1,
        "sweeps":sweeps,
        "false_breakout_candidate":sweeps>0 and outside>0
    }

def gap_setup(d,z):
    if len(d)<3 or not z:
        return False

    p=z["price"]
    t=z["tolerance"]

    for a,b,c in zip(
        d[-12:-2],
        d[-11:-1],
        d[-10:]
    ):

        if (
            b.low>a.high
            and abs(b.close-b.open)>avg_range(d)*0.8
            and abs(p-b.close)<=max(t*3,avg_range(d))
        ):
            return True

        if (
            b.high<a.low
            and abs(b.close-b.open)>avg_range(d)*0.8
            and abs(p-b.close)<=max(t*3,avg_range(d))
        ):
            return True

    return False

def m1_stayel(m1,kind):
    if not m1 or len(m1)<2:
        return None

    p,c=m1[-2],m1[-1]

    if kind=="S":
        return bull_engulf(p,c) or bull_pin(c)

    return bear_engulf(p,c) or bear_pin(c)

def inversion_p02(d,z):
    if not z:
        return False

    f=zone_features(d,z)

    if not f["po2"]:
        return False

    p,t,k=z["price"],z["tolerance"],z["type"]

    for c in d[-8:]:

        if k=="S" and c.close<p-t:
            return True

        if k=="R" and c.close>p+t:
            return True

    return False

def validate_zone(d,z,m1=None):
    if not z:
        return {
            "valid":False,
            "reasons":[]
        }

    k=z["type"]
    f=zone_features(d,z)
    tr=transitions(d,z)

    reasons=[]

    if k=="R":

        if "SBR" in tr:
            reasons.append("SBR")

        if f["po2"]:
            reasons.append("PO2")

        if "SBR" in tr and f["po2"]:
            reasons.append("RSS candidate")

        if inversion_p02(d,z):
            reasons.append("Inversion PO2")

        if f["po2"] and "SBR" in tr:
            reasons.append("I-VR candidate")

        if gap_setup(d,z):
            reasons.append("GAP")

        m1=m1_stayel(m1,"R")

        if m1 is True:
            reasons.append("M1 Stayel")

        if f["fresh"]:
            reasons.append("Fresh")

        return {
            "valid":bool(reasons),
            "reasons":list(dict.fromkeys(reasons)),
            "m1_available":m1 is not None,
            "touched_now":zone_touch(d,z)
        }

    else:

        if "RBS" in tr:
            reasons.append("RBS")

        if f["po2"]:
            reasons.append("PO2")

        if "RBS" in tr and f["po2"]:
            reasons.append("SRR candidate")

        if inversion_p02(d,z):
            reasons.append("Inversion PO2")

        if f["po2"] and "RBS" in tr:
            reasons.append("I-VS candidate")

        if gap_setup(d,z):
            reasons.append("GAP")

        m1=m1_stayel(m1,"S")

        if m1 is True:
            reasons.append("M1 Stayel")

        if f["fresh"]:
            reasons.append("Fresh")

        return {
            "valid":bool(reasons),
            "reasons":list(dict.fromkeys(reasons)),
            "m1_available":m1 is not None,
            "touched_now":zone_touch(d,z)
        }

def analyze(d,m1=None):

    if len(d)<20:
        return {
            "signal":"WAIT",
            "score":0,
            "structure":"UNKNOWN",
            "reasons":["Not enough candles"],
            "zones":[]
        }

    c=d[-1]
    prev=d[-2]

    st=market_structure(d)
    liq=liquidity(d)

    bc=bull_engulf(prev,c) or bull_pin(c)
    sc=bear_engulf(prev,c) or bear_pin(c)

    support=nearest(d,"S")
    resistance=nearest(d,"R")

    zv=[]

    sv=validate_zone(d,support,m1)
    rv=validate_zone(d,resistance,m1)

    if support:
        zv.append({
            **support,
            **sv,
            "direction":"BUY"
        })

    if resistance:
        zv.append({
            **resistance,
            **rv,
            "direction":"SELL"
        })

    buy=list(sv["reasons"]) if support else []
    sell=list(rv["reasons"]) if resistance else []

    if liq["bullish_sweep"]:
        buy.append("Liquidity Sweep")

    if liq["bearish_sweep"]:
        sell.append("Liquidity Sweep")

    if st.startswith("UPTREND"):
        buy.append("HH/HL")

    if st.startswith("DOWNTREND"):
        sell.append("LH/LL")

    if bc:
        buy.append("Bullish Confirmation")

    if sc:
        sell.append("Bearish Confirmation")

    buy=list(dict.fromkeys(buy))
    sell=list(dict.fromkeys(sell))

    # STRICT SNRZ ZONE RULE
    buy_ok=bool(
        support
        and sv["valid"]
        and sv["touched_now"]
        and st.startswith("UPTREND")
        and bc
    )

    sell_ok=bool(
        resistance
        and rv["valid"]
        and rv["touched_now"]
        and st.startswith("DOWNTREND")
        and sc
    )

    signal=(
        "BUY_CANDIDATE"
        if buy_ok
        else "SELL_CANDIDATE"
        if sell_ok
        else "WAIT"
    )

    return {
        "signal":signal,
        "structure":st,
        "price":c.close,
        "confirmation":{
            "bullish":bc,
            "bearish":sc
        },
        "liquidity":liq,
        "reasons":
            buy
            if signal.startswith("BUY")
            else sell
            if signal.startswith("SELL")
            else {
                "buy":buy,
                "sell":sell
            },
        "zones":zv,
        "mode":"paper/educational",
        "method":"SNRZ-only",
        "rule":
            "Zone + SNRZ condition + current price touch + "
            "structure + candle confirmation"
    }

def multi_timeframe(all_data):

    result={}

    for tf,d in all_data.items():

        m1=(
            all_data.get("1m")
            if tf in ("5m","15m")
            else None
        )

        result[tf]=analyze(d,m1)

    return {
        "engine":"SNRZ AI V9",
        "method":"SNRZ-only",
        "mode":"paper/educational",
        "analysis":result
    }
