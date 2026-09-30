from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from market import candles
from snrz_engine import Candle, multi_timeframe
from openai import AsyncOpenAI
import os, json

app = FastAPI(title="SNRZ AI V9 ChatGPT", version="9.2")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")

SYSTEM_PROMPT = """
You are the SNRZ AI explanation layer inside an educational/paper-trading website.

Use ONLY the SNRZ framework and terminology supplied by the website:
S, R, SBR, RBS, V.S, V.R, I-VS, I-VR, PO2, SRR, RSS,
Fresh, False Breakout, Liquidity Sweep, Liquidity Run, Pump Base,
Drop Base, GAP Strategy, market structure, and confirmation.

Explain the dashboard analysis clearly. Do not invent a zone or signal that is not present
in the supplied analysis. If the data is insufficient, say WAIT / insufficient confirmation.

This website is educational and paper/simulation only. Do not execute trades, connect to a broker,
request credentials, promise profits, or claim certainty. Do not give guaranteed BUY/SELL advice.
"""

TIMEFRAMES = ["1mo", "1w", "1d", "4h", "1h", "30m", "15m", "5m"]


class AskRequest(BaseModel):
    question: str = ""
    analysis: dict = {}


@app.get("/health")
async def health():
    return {
        "ok": True,
        "chatgpt": bool(os.getenv("OPENAI_API_KEY")),
        "model": OPENAI_MODEL,
    }


@app.get("/", response_class=HTMLResponse)
async def home():
    return HTMLResponse("""
<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SNRZ AI V9</title>
<style>
body{margin:0;background:#06111f;color:#eaf2ff;font-family:-apple-system,BlinkMacSystemFont,Arial;padding:22px}
h1{font-size:38px;margin:5px 0}.sub{color:#91a6c1;font-size:18px;margin-bottom:20px}
.card{background:#0c1b2e;border:1px solid #234365;border-radius:22px;padding:20px;margin:15px 0}
button{border:0;border-radius:13px;padding:14px 20px;font-size:17px;font-weight:700}
input,textarea{width:100%;box-sizing:border-box;background:#081628;color:#fff;border:1px solid #294967;border-radius:14px;padding:14px;font-size:16px}
textarea{min-height:110px}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}
.tf{border:1px solid #234365;border-radius:16px;padding:15px}.wait{color:#c9d5e5}.up{color:#7ee787}.down{color:#ff9b9b}
pre{white-space:pre-wrap;font-family:inherit;line-height:1.55}
@media(max-width:600px){.grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<h1>SNRZ AI V9</h1>
<div class="sub">SNRZ-only â¢ Multi-Timeframe â¢ Paper/Educational â¢ ChatGPT</div>

<div class="card">
<button onclick="loadAnalysis()">Refresh</button>
<div id="price" style="font-size:42px;font-weight:800;margin-top:18px">Loadingâ¦</div>
</div>

<div class="card">
<h2>Multi-Timeframe Analysis</h2>
<div id="mtf" class="grid"></div>
</div>

<div class="card">
<h2>ð¤ Ask SNRZ AI</h2>
<textarea id="q" placeholder="Example: Explain the current SNRZ analysis and why the dashboard says WAIT."></textarea>
<br><br>
<button onclick="askAI()">Ask SNRZ AI</button>
<div id="answer" style="margin-top:18px"></div>
</div>

<script>
let latest={};

async function loadAnalysis(){
  document.getElementById("price").textContent="Loadingâ¦";
  try{
    const r=await fetch("/multi-analysis");
    latest=await r.json();
    document.getElementById("price").textContent =
      "XAUUSD " + (latest.price ?? "â");

    const data=latest.timeframes || latest.analysis || {};
    document.getElementById("mtf").innerHTML =
      Object.entries(data).map(([tf,x])=>{
        const trend=x.trend || x.structure || "â";
        const signal=x.signal || "WAIT";
        return `<div class="tf">
          <b style="font-size:20px">${tf.toUpperCase()}</b>
          <div style="font-size:24px;font-weight:800;margin-top:8px">${signal}</div>
          <div>${trend}</div>
          <div class="wait">${x.reason || "No active confirmation"}</div>
        </div>`;
      }).join("");
  }catch(e){
    document.getElementById("price").textContent="No market data";
  }
}

async function askAI(){
  const answer=document.getElementById("answer");
  answer.textContent="Thinkingâ¦";
  try{
    const r=await fetch("/ask-ai",{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({
        question:document.getElementById("q").value,
        analysis:latest
      })
    });
    const d=await r.json();
    answer.innerHTML="<pre>"+escapeHtml(d.answer || d.detail || "No answer")+"</pre>";
  }catch(e){
    answer.textContent="AI connection error.";
  }
}

function escapeHtml(s){
  return String(s).replaceAll("&","&amp;").replaceAll("<","&lt;")
    .replaceAll(">","&gt;").replaceAll('"',"&quot;");
}

loadAnalysis();
</script>
</body>
</html>
""")


@app.get("/multi-analysis")
async def multi_analysis():
    all_data = {}
    for tf in TIMEFRAMES:
        try:
            all_data[tf] = candles("XAUUSD", tf)
        except Exception:
            all_data[tf] = []

    result = multi_timeframe(all_data)
    return result


@app.post("/ask-ai")
async def ask_ai(req: AskRequest):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="OPENAI_API_KEY is not configured on the backend."
        )

    question = req.question.strip() or "Explain the current SNRZ analysis."
    payload = json.dumps(req.analysis, ensure_ascii=False, default=str)

    client = AsyncOpenAI(api_key=api_key)

    response = await client.responses.create(
        model=OPENAI_MODEL,
        instructions=SYSTEM_PROMPT,
        input=f"""
User question:
{question}

Current dashboard analysis:
{payload}
"""
    )

    return {"answer": response.output_text}
