"""
FRANCINE SCREENER v2 — Master Options & Fundamentals Screener
Screens the S&P 500 using Francine's updated institutional methodology.
"""
import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import time
import io
from datetime import datetime

st.set_page_config(page_title="Francine Screener v2", page_icon="★", layout="centered", initial_sidebar_state="collapsed")

EXCLUDED_INDUSTRIES = ["banks","banking","bank","insurance","insurer","pharmaceuticals","pharmaceutical","pharma","tobacco","marijuana","cannabis","vaping","lending","consumer lending","mortgage","financial services","diversified financial","asset management"]
EXCLUDED_SECTORS = ["financial services","banks","insurance"]
EXCLUDED_COUNTRIES = ["china","russia","north korea","brazil","argentina","mexico","chile","colombia","peru","venezuela"]
PRIORITY_COUNTRIES = ["united states","canada","united kingdom","germany","france","switzerland","netherlands","sweden","denmark","finland","norway","belgium","spain","italy","ireland","australia","new zealand","japan","south korea","austria","luxembourg","singapore","israel"]
# MAX_QUALIFIED = 20 — removed; show all qualified companies per Francine's spec

@st.cache_data(ttl=3600)
def get_index_tickers(index_name):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"}
        urls = {
            "S&P 500": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
            "S&P 400": "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies",
            "S&P 600": "https://en.wikipedia.org/wiki/List_of_S%26P_600_companies",
        }
        resp = requests.get(urls[index_name], headers=headers, timeout=15)
        resp.raise_for_status()
        df = pd.read_html(io.StringIO(resp.text))[0]
        return df["Symbol"].str.replace(".","-",regex=False).tolist()
    except Exception as e:
        st.error(f"Failed to load {index_name}: {e}")
        return []

@st.cache_data(ttl=3600)
def get_rest_of_market_tickers():
    """Load liquid US-listed symbols from Nasdaq's public screener endpoint."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://www.nasdaq.com",
            "Referer": "https://www.nasdaq.com/",
        }
        resp = requests.get(
            "https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=10000&market=stocks",
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        rows = (resp.json().get("data") or {}).get("rows") or []
        return [row["symbol"].replace(".", "-") for row in rows if row.get("symbol")]
    except Exception as e:
        st.warning(f"Could not load the rest of the market: {e}")
        return []

def get_universe_tickers(universe):
    if universe == "S&P 500":
        return get_index_tickers("S&P 500")
    if universe == "S&P 400":
        return get_index_tickers("S&P 400")
    if universe == "S&P 600":
        return get_index_tickers("S&P 600")
    if universe == "Rest of Market":
        return get_rest_of_market_tickers()

    seen = set()
    tickers = []
    for tier in ("S&P 500", "S&P 400", "S&P 600", "Rest of Market"):
        for ticker in get_universe_tickers(tier):
            if ticker not in seen:
                seen.add(ticker)
                tickers.append(ticker)
    return tickers

def passes_industry(info):
    s = (info.get("sector") or "").lower(); i = (info.get("industry") or "").lower()
    for e in EXCLUDED_SECTORS:
        if e in s: return False, f"Excluded sector: {info.get('sector')}"
    for e in EXCLUDED_INDUSTRIES:
        if e in i: return False, f"Excluded industry: {info.get('industry')}"
    return True, ""

def passes_geo(info):
    c = (info.get("country") or "").lower()
    if not c: return False, "No country data"
    for e in EXCLUDED_COUNTRIES:
        if e in c: return False, f"Excluded country: {info.get('country')}"
    return True, ""

def passes_price(info, lo, hi):
    p = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
    if p is None: return False, "No price", None
    if p < lo or p > hi: return False, f"${p:.2f} outside range", p
    return True, "", p

def get_iv(ticker):
    try:
        s = yf.Ticker(ticker); eds = s.options
        if not eds: return None,None
        px = s.info.get("currentPrice") or s.info.get("regularMarketPrice")
        if not px: return None,None
        for exp in eds[:10]:
            try:
                o = s.option_chain(exp); c = o.calls; p = o.puts
                if not c.empty:
                    c["d"]=abs(c["strike"]-px); nc=c.loc[c["d" ].idxmin()]; ivc=nc.get("impliedVolatility")
                    if not p.empty:
                        p["d"]=abs(p["strike"]-px); np=p.loc[p["d" ].idxmin()]; ivp=np.get("impliedVolatility")
                        iv=(ivc+ivp)/2 if ivc and ivp else ivc or ivp
                    else: iv=ivc
                    if iv and iv>0.05: return float(iv)*100, f"Chain {exp}"
            except: pass
        return None,None
    except: return None,None

def check_options(ticker):
    try:
        s=yf.Ticker(ticker); eds=s.options
        if not eds or len(eds)<2: return False,0,0
        o=s.option_chain(eds[0]); c=o.calls; p=o.puts
        if c.empty or p.empty: return False,len(eds),0
        wk=0
        for exp in eds[:10]:
            try:
                ch=s.option_chain(exp)
                if (ch.calls["volume"].sum()+ch.puts["volume"].sum())>0: wk+=1
            except: pass
        tv=int(c["volume"].sum()+p["volume"].sum())
        return wk>=2,len(eds),tv
    except: return False,0,0

def get_margins(ticker):
    try:
        s=yf.Ticker(ticker); ix=s.financials
        if ix is None or ix.empty: return None,None
        yr=ix.iloc[:,0]; oi=None; rev=None
        for k in ["Operating Income","EBIT","Operating Profit"]:
            if k in yr.index: oi=float(yr.loc[k]); break
        for k in ["Total Revenue","Revenue"]:
            if k in yr.index: rev=float(yr.loc[k]); break
        if oi is not None and rev and rev!=0: return (oi/rev)*100,ix.columns[0]
        return None,None
    except: return None,None

def get_cagr(ticker):
    try:
        s=yf.Ticker(ticker); ix=s.financials
        if ix is None or ix.empty or ix.shape[1]<3: return None,None
        revs=[]
        for i in range(min(4,ix.shape[1])):
            col=ix.iloc[:,i]
            for k in ["Total Revenue","Revenue"]:
                if k in col.index: revs.append(float(col.loc[k])); break
            else: revs.append(None)
        revs=[r for r in revs if r]
        if len(revs)<3: return None,None
        n=len(revs)-1
        if revs[-1]<=0 or revs[0]<=0: return None,None
        return round(((revs[0]/revs[-1])**(1.0/n)-1)*100,2),f"{n}-yr CAGR"
    except: return None,None

def get_summary(info,ticker):
    s=info.get("longBusinessSummary") or ""
    if s:
        ss=". ".join(x.strip() for x in s.replace("\n"," ").split(".")[:3] if x.strip())
        return ss[:250]+("..." if len(ss)>250 else "")
    return f"{ticker}"

SCAN_SVG = """<div class="scan-wrap"><svg width="200" height="200" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
<defs><linearGradient id="sweepg" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#1a6b3c" stop-opacity="0"/><stop offset="1" stop-color="#2ecc71" stop-opacity="0.8"/></linearGradient></defs>
<circle cx="100" cy="100" r="90" fill="none" stroke="#1a6b3c" stroke-opacity="0.5"/>
<circle cx="100" cy="100" r="60" fill="none" stroke="#1a6b3c" stroke-opacity="0.4"/>
<circle cx="100" cy="100" r="30" fill="none" stroke="#1a6b3c" stroke-opacity="0.3"/>
<line x1="10" y1="100" x2="190" y2="100" stroke="#1a6b3c" stroke-opacity="0.3"/>
<line x1="100" y1="10" x2="100" y2="190" stroke="#1a6b3c" stroke-opacity="0.3"/>
<circle class="scan-ping" cx="100" cy="100" r="6" fill="none" stroke="#2ecc71"/>
<circle class="scan-ping p2" cx="100" cy="100" r="6" fill="none" stroke="#2ecc71"/>
<g class="scan-sweep"><path d="M100 100 L190 100 A90 90 0 0 0 163.6 36.4 Z" fill="url(#sweepg)" transform="rotate(45 100 100)"/></g>
<circle class="scan-blip" cx="140" cy="70" r="3" fill="#2ecc71"/>
<circle class="scan-blip" style="animation-delay:0.7s" cx="65" cy="125" r="3" fill="#2ecc71"/>
<circle class="scan-blip" style="animation-delay:1.4s" cx="115" cy="150" r="3" fill="#2ecc71"/>
<circle cx="100" cy="100" r="4" fill="#2ecc71"/>
</svg></div>"""

def progress_svg(frac):
    w = max(0.0, min(frac, 1.0)) * 300
    return (f'<svg width="100%" height="14" viewBox="0 0 300 14" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">'
            f'<defs><clipPath id="pc"><rect x="0" y="0" width="{w:.1f}" height="14" rx="7"/></clipPath></defs>'
            f'<rect width="300" height="14" rx="7" fill="#1a6b3c" fill-opacity="0.2"/>'
            f'<g clip-path="url(#pc)"><rect width="300" height="14" fill="#1a6b3c"/>'
            f'<rect class="scan-shimmer" width="40" height="14" fill="#fff" fill-opacity="0.25"/></g></svg>')

def screen(ticker, lo, hi, iv_tgt, iv_lo, iv_hi, min_vol):
    r={"ticker":ticker,"ok":False,"reason":"","name":"","sector":"","industry":"","price":None,"iv":None,"vol":0,"has_wk":False,"num_exp":0,"opt_vol":0,"margin":None,"cagr":None,"driver":"","log":[]}
    def log(m): r["log"].append(m)
    try:
        s=yf.Ticker(ticker); info=s.info
        if not info or (info.get("regularMarketPrice") is None and info.get("currentPrice") is None):
            r["reason"]="No price"; log("FAIL - no price"); return r
        r["name"]=info.get("longName") or info.get("shortName") or ticker
        r["sector"]=info.get("sector") or "N/A"; r["industry"]=info.get("industry") or "N/A"
        log(f"{r['name']} ({ticker}) - {r['sector']}/{r['industry']}")

        ok,re=passes_industry(info)
        if not ok: r["reason"]=re; log(f"FAIL - {re}"); return r

        ok,re=passes_geo(info)
        if not ok: r["reason"]=re; log(f"FAIL - {re}"); return r

        ok,re,px=passes_price(info,lo,hi)
        if not ok: r["reason"]=re; log(f"FAIL - {re}"); return r
        r["price"]=px; log(f"PASS price ${px:.2f}")

        hw,ne,ov=check_options(ticker)
        r["has_wk"]=hw; r["num_exp"]=ne; r["opt_vol"]=ov
        if not hw: r["reason"]="No weekly options"; log(f"FAIL - no weekly chain ({ne} exp)"); return r
        log(f"PASS - {ne} expirations, vol {ov:,}")

        iv,ivs=get_iv(ticker)
        if iv is None: r["reason"]="No IV data"; log("FAIL - no IV"); return r
        r["iv"]=round(iv,1)
        if iv<iv_lo or iv>iv_hi: r["reason"]=f"IV {iv:.1f}% outside {iv_lo:.0f}-{iv_hi:.0f}%"; log(f"FAIL - IV {iv:.1f}%"); return r
        log(f"PASS - IV {iv:.1f}% (target ~{iv_tgt:.0f}%)")

        adv=int(info.get("averageVolume") or info.get("averageDailyVolume10Day") or 0)
        r["vol"]=adv
        if adv<min_vol: r["reason"]=f"Vol {adv:,}<{min_vol:,}"; log(f"FAIL - vol {adv:,}"); return r
        log(f"PASS - vol {adv:,}")

        om,oy=get_margins(ticker)
        if om is None: r["reason"]="No margin data"; log("FAIL - no margin"); return r
        r["margin"]=round(om,2)
        if om<=0: r["reason"]=f"Margin {om:.1f}% negative"; log(f"FAIL - margin {om:.1f}%"); return r
        log(f"PASS - margin {om:.1f}%")

        cg,_=get_cagr(ticker); r["cagr"]=cg
        r["driver"]=get_summary(info,ticker)
        r["ok"]=True; log("✅ QUALIFIED ★")
        return r
    except Exception as e:
        r["reason"]=f"Error: {e}"; log(f"FAIL - {e}"); return r

# ── UI ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-title { font-size:1.8rem; font-weight:700 }
    .subtitle { color:#888; margin-bottom:1.5rem }
    .fc-badge { display:inline-block; background:#1a6b3c; color:#fff; padding:0.15rem 0.6rem; border-radius:12px; font-size:0.8rem; font-weight:600 }
    div[data-testid="stStatusWidget"] { display:none !important }
    .scan-wrap { display:flex; justify-content:center; margin:0.5rem 0 }
    .scan-sweep { transform-origin:100px 100px; animation:scan-spin 2.4s linear infinite }
    .scan-ping { transform-origin:center; animation:scan-ping 2.4s ease-out infinite }
    .scan-ping.p2 { animation-delay:0.8s }
    .scan-blip { animation:scan-blip 2.4s ease-in-out infinite }
    .scan-shimmer { animation:scan-shimmer 1.4s linear infinite }
    @keyframes scan-spin { to { transform:rotate(360deg) } }
    @keyframes scan-ping { 0% { opacity:0.7; r:6 } 100% { opacity:0; r:70 } }
    @keyframes scan-blip { 0%,100% { opacity:0.15 } 50% { opacity:1 } }
    @keyframes scan-shimmer { from { transform:translateX(-40px) } to { transform:translateX(300px) } }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">★ FRANCINE SCREENER v2</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Master Options & Fundamentals Screener — Institutional Quantitative Analysis</div>', unsafe_allow_html=True)

st.markdown("### Universe")
universe = st.radio(
    "Choose:",
    ["S&P 500", "S&P 400", "S&P 600", "Rest of Market", "All Tiers Progressive"],
    format_func=lambda value: {
        "S&P 500": "S&P 500 — Large Cap (~503 stocks)",
        "S&P 400": "S&P 400 — Mid Cap (~400 stocks)",
        "S&P 600": "S&P 600 — Small Cap (~603 stocks)",
        "Rest of Market": "Rest of Market — Other US-listed stocks",
        "All Tiers Progressive": "All Tiers Progressive (1>2>3>4)",
    }[value],
)

st.markdown("### Parameters")
c1,c2=st.columns(2)
with c1: lo=st.number_input("From ($)",1.0,5000.0,10.0,1.0)
with c2: hi=st.number_input("To ($)",1.0,5000.0,50.0,1.0)

st.markdown("---")
st.markdown("### Phase 2: Core Filtering Parameters")
c1,c2,c3=st.columns(3)
with c1: iv_tgt=st.number_input("IV Target (%)",5.0,100.0,32.0,1.0)
with c2: iv_lo=st.number_input("IV Min (%)",5.0,100.0,28.0,1.0)
with c3: iv_hi=st.number_input("IV Max (%)",5.0,150.0,48.0,1.0)
min_vol=st.number_input("Min Avg Daily Volume (shares)",100000,100000000,2000000,100000,format="%d")

tab1,tab2=st.tabs(["🔍 Run Screen","📖 Info"])

with tab1:
    if st.button("🚀 RUN FRANCINE SCREEN v2",type="primary",use_container_width=True):
        if lo<=0 or hi<=0: st.error("Enter valid price range.")
        elif lo>=hi: st.error("To: must be greater than From:.")
        elif iv_lo>=iv_hi: st.error("IV Min must be less than IV Max.")
        else:
            with st.spinner(f"Loading {universe}..."): tickers=get_universe_tickers(universe)
            if not tickers: st.stop()
            st.info(f"Scanning {len(tickers):,} stocks — ${lo:.0f}-${hi:.0f}, IV {iv_lo:.0f}-{iv_hi:.0f}%, vol ≥{min_vol:,}")
            anim=st.empty(); anim.markdown(SCAN_SVG,unsafe_allow_html=True)
            pb=st.empty(); stx=st.empty()
            ok=[]; out=[]
            for i,t in enumerate(tickers):
                pb.markdown(progress_svg((i+1)/len(tickers)),unsafe_allow_html=True)
                stx.text(f"[{i+1}/{len(tickers)}] {t} — {len(ok)} qualified, {len(out)} excluded")
                r=screen(t,lo,hi,iv_tgt,iv_lo,iv_hi,min_vol)
                if r["ok"]: ok.append(r)
                else: out.append(r)
                if i%4==0: time.sleep(0.05)
            anim.empty(); pb.markdown(progress_svg(1.0),unsafe_allow_html=True); stx.text(f"Done — {len(ok)} qualified, {len(out)} excluded of {len(tickers):,}")
            st.markdown("---")

            if not ok:
                st.warning("No companies pass all filters. Try widening the range.")
                rc={}
                for s in out:
                    cat=(s["reason"][:80] if s["reason"] else "Unknown").split("(")[0].strip()
                    rc[cat]=rc.get(cat,0)+1
                for rea,cnt in sorted(rc.items(),key=lambda x:-x[1])[:15]:
                    st.markdown(f"- **{rea}** → {cnt} companies")
            else:
                st.markdown(f"### ✅ QUALIFIED — Francine Core ★")
                td=[]
                for q in ok:
                    td.append({"Ticker":q["ticker"],"Company":q["name"],"Price":f"${q['price']:.2f}","30D IV":f"{q['iv']:.1f}%" if q['iv'] else "N/A","Avg Vol":f"{q['vol']:,}","3Y CAGR":f"{q['cagr']:.1f}%" if q['cagr'] is not None else "N/A","Catalyst":(q['driver'][:120]+"...") if len(q.get('driver',''))>120 else (q['driver'] or "N/A")})
                st.dataframe(pd.DataFrame(td),hide_index=True,use_container_width=True)

                st.markdown("---")
                st.markdown("### 🏆 Top Picks for Income Strategies")
                top=sorted(ok,key=lambda q:((q.get('cagr') or 0),(q.get('margin') or 0)),reverse=True)[:3]
                for i,q in enumerate(top,1):
                    c=f"{q['cagr']:.1f}% CAGR" if q.get('cagr') else "N/A"
                    st.markdown(f"{i}. **{q['ticker']}** — {q['name']} — ${q['price']:.2f}, IV {q['iv']:.1f}%, {c}, margin {q['margin']:.1f}%")

                st.markdown("---")
                st.markdown("### 🔍 Screened-Out Summary")
                rc={}
                for s in out:
                    cat=(s["reason"][:80] if s["reason"] else "Unknown").split("(")[0].strip().rstrip("— ")
                    rc[cat]=rc.get(cat,0)+1
                for rea,cnt in sorted(rc.items(),key=lambda x:-x[1]):
                    st.markdown(f"- **{rea}** → {cnt} companies")
                st.markdown(f"_{len(out):,} of {len(tickers):,} excluded._")

with tab2:
    st.markdown("""
    **What it does:** Screens selected US-market tiers using Francine's v2 methodology.

    **Universes:** S&P 500 large caps, S&P 400 mid caps, S&P 600 small caps,
    the remaining Nasdaq-listed market, or all four tiers progressively.

    **Filters (all must pass):**
    1. Industry exclusion — no banks, insurance, pharma, etc.
    2. Geographic — developed markets only
    3. Price range — user defined
    4. Weekly options — Cboe Weeklys verified
    5. IV — within target window (default 28-48%)
    6. Volume — avg daily ≥ 2M shares
    7. Operating margins — positive (latest year)
    8. Revenue CAGR — calculated (informational)

    **Data source:** Yahoo Finance (yfinance) — live market data.
    """[:500])