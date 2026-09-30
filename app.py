from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from market import candles
from snrz_engine import Candle, multi_timeframe

app = FastAPI(title="SNRZ AI V7", version="7.1")

HTML = """<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SNRZ AI V7</title>

<style>
body{
    margin:0;
    background:#07111f;
    color:#eaf2ff;
    font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif
}
.wrap{
    max-width:1050px;
    margin:auto;
    padding:18px
}
h1{margin:0}
.muted{color:#91a4bd}
.card{
    background:#0d1b2d;
    border:1px solid #223955;
    border-radius:16px;
    padding:16px;
    margin:14px 0
}
.grid{
    display:grid;
    grid-template-columns:repeat(4,1fr);
    gap:10px
}
.tf{
    background:#091524;
    border:1px solid #20344e;
    border-radius:12px;
    padding:12px
}
.sig{
    font-weight:800;
    margin:8px 0
}
.buy{color:#70e59c}
.sell{color:#ff8191}
.wait{color:#cbd5e1}
button{
    padding:10px 15px;
    border:0;
    border-radius:10px;
    font-weight:700
}
.price{
    font-size:32px;
    font-weight:800
}
@media(max-width:700px){
    .grid{grid-template-columns:repeat(2,1fr)}
}
</style>
</head>

<body>
<div class="wrap">

<h1>SNRZ AI V7</h1>
<div class="muted">
SNRZ-only • Multi-Timeframe • Paper/Educational
</div>

<div class="card">
<button onclick="load()">Refresh</button>
<div class="muted">XAUUSD</div>
<div id="price" class="price">—</div>
</div>

<div class="card">
<b>Multi-Timeframe Analysis</b>
<div id="grid" class="grid">Loading…</div>
</div>

<div class="card">
<div class="muted">
SNRZ concepts used by the engine include market structure,
confirmation, liquidity sweep/run, V.S, V.R, RBS, SBR,
SRR, RSS and PO2. A concept is shown as live only when
the backend detects it.
</div>
</div>

</div>

<script>
async function load(){

    let g=document.getElementById('grid');

    try{

        let r=await fetch('/multi-analysis',{
            cache:'no-store'
        });

        let d=await r.json();

        if(!r.ok)
            throw Error(d.detail||'API error');

        let a=d.analysis||{};
        let t=d.timeframes||Object.keys(a);

        let p=null;

        g.innerHTML=t.map(k=>{

            let x=a[k]||{};

            if(p==null && x.price!=null)
                p=x.price;

            let s=x.signal||'WAIT';

            let c=s.includes('BUY')
                ?'buy'
                :s.includes('SELL')
                ?'sell'
                :'wait';

            let q=Array.isArray(x.reason)
                ?x.reason.join(' • ')
                :'';

            return `
            <div class="tf">
                <b>${k.toUpperCase()}</b>

                <div class="sig ${c}">
                    ${s.replaceAll('_',' ')}
                </div>

                <div class="muted">
                    ${x.structure||'—'}
                </div>

                <small>
                    ${q||'No active confirmation'}
                </small>
            </div>
            `;

        }).join('');

        document.getElementById('price').textContent=
            p==null
            ?'—'
            :Number(p).toFixed(2);

    }catch(e){

        g.innerHTML=
            '<span>'+e.message+'</span>';

    }
}

load();
</script>

</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def root():
    return HTML


@app.get("/health")
def health():
    return {
        "ok": True,
        "engine": "SNRZ AI V7",
        "mode": "paper/educational",
        "method": "SNRZ-only",
        "status": "online"
    }


@app.get("/multi-analysis")
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
        "5m"
    ]

    for tf in timeframes:

        try:

            raw = await candles(tf, 250)

            all_data[tf] = [
                Candle(**x)
                for x in raw
            ]

        except Exception as e:

            errors[tf] = str(e)

    if not all_data:

        raise HTTPException(
            status_code=502,
            detail="No market data. Configure TWELVE_DATA_API_KEY on the backend."
        )

    result = multi_timeframe(all_data)

    result.update({
        "engine": "SNRZ AI V7",
        "mode": "paper/educational",
        "method": "SNRZ-only",
        "timeframes": timeframes,
        "errors": errors
    })

    return result
