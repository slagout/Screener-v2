"""
FRANCINE SCREENER V3 — Tiered Desktop App
=========================================
V2's EXACT screening logic + tiered UI — NO industry exclusions.
All industry/sector/name blocks from V2 removed per Tom's directive.
Identical to V2 (francine_current_discovery.py) in deep_screen, IV calc,
margin, volume, CAGR, and options-liquidity checks.
"""
import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import io
import time
import re
import html
import os
import sys
from datetime import datetime, timedelta
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

st.set_page_config(page_title="Francine Screener V3", page_icon="📊", layout="wide", initial_sidebar_state="expanded")

# ── ALL INDUSTRY/SECTOR/NAME EXCLUSIONS REMOVED per Tom's directive ──
# V3 scans ALL industries: pharma, banks, insurance, tobacco, cannabis,
# REITs, financial services no longer blocked.
EXCLUDED_COUNTRIES = [
    "china", "russia", "north korea", "brazil", "argentina",
    "mexico", "chile", "colombia", "peru", "venezuela",
]
DEFAULT_PRICE_MIN = 10.0
DEFAULT_PRICE_MAX = 50.0
DEFAULT_IV_MIN = 28.0
DEFAULT_IV_MAX = 48.0
DEFAULT_MIN_VOLUME = 2_000_000
DEEP_SCREEN_WORKERS = 8
SCREEN_CACHE_TTL = 3600


@st.cache_resource
def _screen_cache():
    return {}

# ── Tier definitions ──────────────────────────────────────────────────
TIERS = {
    "S&P 500":  {"label":"Tier 1 — S&P 500","desc":"~503 stocks","color":"#42a5f5"},
    "S&P 400":  {"label":"Tier 2 — S&P 400","desc":"~400 stocks","color":"#66bb6a"},
    "S&P 600":  {"label":"Tier 3 — S&P 600","desc":"~600 stocks","color":"#f9a825"},
    "Rest":     {"label":"Tier 4 — Rest of Market","desc":"~5,500 stocks","color":"#ab47bc"},
}

# ── Tier loaders (V2 exact) ────────────────────────────────────────────
def load_index(name):
    pages = {"S&P 500":"https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
             "S&P 400":"https://en.wikipedia.org/wiki/List_of_S%26P_400_companies",
             "S&P 600":"https://en.wikipedia.org/wiki/List_of_S%26P_600_companies"}
    url = pages.get(name)
    if not url: return [], {}
    h = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"}
    for attempt in range(2):
        try:
            r = requests.get(url, headers=h, timeout=30)
            r.raise_for_status()
            df = pd.read_html(io.StringIO(r.text))[0]
            tk = df["Symbol"].str.replace(".","-",regex=False).tolist()
            sc = "GICS Sector" if "GICS Sector" in df.columns else df.columns[2]
            sectors = dict(zip(tk, df[sc].fillna("").tolist()))
            return tk, sectors
        except Exception as e:
            if attempt == 0:
                time.sleep(2)
                continue
            st.warning(f"Could not load {name} (attempt {attempt+1}): {e}")
            return [], {}

@st.cache_data(ttl=3600)
def get_tickers(name): return load_index(name)[0]

def get_rest_tickers(exclude):
    return _rest_tickers(frozenset(exclude))

@st.cache_data(ttl=3600, show_spinner=False)
def _rest_tickers(exclude):
    tk = set(); h = {"User-Agent":"Mozilla/5.0"}
    for url,label in [("https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt","NASDAQ"),
                      ("https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt","NYSE/AMEX")]:
        try:
            r = requests.get(url,headers=h,timeout=30); r.raise_for_status()
            lines = r.text.strip().split("\n")
            dl = [l for l in lines if l and not l.startswith("File Creation")]
            if len(dl)<2: continue
            cols = dl[0].split("|" if "|" in dl[0] else "\t")
            cm = {c.strip().lower():i for i,c in enumerate(cols)}
            si = cm.get("symbol", cm.get("act symbol",0))
            ti = cm.get("test issue",None); ei = cm.get("etf",None)
            for line in dl[1:]:
                p = line.split("|" if "|" in line else "\t")
                if len(p)<=si: continue
                s = p[si].strip().replace(".","-")
                if not re.match(r"^[A-Z0-9-]{1,5}$",s): continue
                if ti and len(p)>ti and p[ti].strip().upper()=="Y": continue
                if ei and len(p)>ei and p[ei].strip().upper()=="Y": continue
                if s in exclude: continue
                tk.add(s)
        except: pass
    return sorted(tk)

# ── V2 EXACT filter functions ─────────────────────────────────────────
def industry_pass(info):
    """All industries allowed — exclusions removed per V3 spec."""
    return True

def geo_pass(info):
    c = (info.get("country") or "").lower()
    if not c: return True
    for e in EXCLUDED_COUNTRIES:
        if e in c: return False
    return True

# ── V2 EXACT tier_name_filter ─────────────────────────────────────────
def tier_name_filter(tickers, sectors, name_map):
    """First-pass filter — no industry/sector exclusions in V3."""
    return list(tickers)

# ── V2 EXACT deep_screen ──────────────────────────────────────────────
def deep_screen(ticker, price, iv_min, iv_max, min_vol):
    result = {
        "ticker": ticker, "qualified": False, "fail_reason": "",
        "company_name": "", "sector": "", "industry": "",
        "price": price, "iv": None, "volume": 0,
        "avg_volume": 0, "margin": None, "cagr": None,
        "driver": "", "options_liquid": False,
    }
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        if not info:
            result["fail_reason"] = "No data"
            return result

        result["company_name"] = info.get("longName") or info.get("shortName") or ticker
        result["sector"] = info.get("sector") or "N/A"
        result["industry"] = info.get("industry") or "N/A"

        # Industry/sector/name filter
        if not industry_pass(info):
            result["fail_reason"] = "Industry excluded"
            return result
        if not geo_pass(info):
            result["fail_reason"] = "Geography excluded"
            return result

        # Cheap volume check first to skip option-chain calls
        avg_vol = int(info.get("averageVolume") or info.get("averageDailyVolume10Day") or 0)
        yahoo_err = ""
        if not avg_vol:
            # Yahoo sometimes returns a partial info dict; fall back to price history
            try:
                hist = stock.history(period="3mo")
                if not hist.empty:
                    avg_vol = int(hist["Volume"].mean())
                else:
                    yahoo_err = " (Yahoo Finance returned no history)"
            except Exception as e:
                yahoo_err = f" (Yahoo Finance error: {type(e).__name__}: {str(e)[:120]})"
        result["avg_volume"] = avg_vol
        result["volume"] = avg_vol
        if avg_vol < min_vol:
            result["fail_reason"] = f"Avg volume {avg_vol:,} < {min_vol:,}{yahoo_err}"
            return result

        # Options liquidity check (need 2+ weeklies with volume)
        exp_dates = ()
        opt_err = ""
        for attempt in range(3):
            try:
                exp_dates = stock.options
                if exp_dates:
                    break
                opt_err = " (Yahoo Finance returned no expirations, likely throttled)"
            except Exception as e:
                opt_err = f" (Yahoo Finance error: {type(e).__name__}: {str(e)[:120]})"
            time.sleep(1.5 * (attempt + 1))
        if not exp_dates or len(exp_dates) < 2:
            result["fail_reason"] = f"No weekly options chain{opt_err}"
            return result

        weeks_with_volume = 0
        for exp in exp_dates[:10]:
            try:
                chain = stock.option_chain(exp)
                if (chain.calls["volume"].sum() + chain.puts["volume"].sum()) > 0:
                    weeks_with_volume += 1
                    if weeks_with_volume >= 2:
                        break
            except Exception:
                pass
        if weeks_with_volume < 2:
            result["fail_reason"] = "Low options activity"
            return result
        result["options_liquid"] = True

        # IV calculation (V2 exact: custom formula → yfinance fallback)
        iv_found = False
        now = datetime.now()
        target_30d = now + timedelta(days=30)

        try:
            best_exp = min(exp_dates, key=lambda e: abs(
                (datetime.strptime(e[:10], "%Y-%m-%d") - target_30d).days))
            chain_30d = stock.option_chain(best_exp)
            tte = (datetime.strptime(best_exp[:10], "%Y-%m-%d") - now).days / 365.0

            if not chain_30d.calls.empty:
                chain_30d.calls["dist"] = abs(chain_30d.calls["strike"] - price)
                nearest_call = chain_30d.calls.loc[chain_30d.calls["dist"].idxmin()]
                call_mid = (float(nearest_call.get("bid", 0)) + float(nearest_call.get("ask", 0))) / 2
                call_price = call_mid if call_mid > 0.01 else float(nearest_call.get("lastPrice", 0))
                if call_price > 0.01 and tte > 0.001:
                    iv_approx = call_price / (price * 0.4 * (tte ** 0.5))
                    if 0.01 < iv_approx < 5.0:
                        iv_pct = iv_approx * 100
                        if iv_min <= iv_pct <= iv_max:
                            result["iv"] = round(iv_pct, 1)
                            iv_found = True
                        else:
                            result["fail_reason"] = f"IV {iv_pct:.1f}% outside {iv_min}-{iv_max}% range"
                            return result

            if not iv_found and not chain_30d.puts.empty:
                chain_30d.puts["dist"] = abs(chain_30d.puts["strike"] - price)
                nearest_put = chain_30d.puts.loc[chain_30d.puts["dist"].idxmin()]
                put_mid = (float(nearest_put.get("bid", 0)) + float(nearest_put.get("ask", 0))) / 2
                put_price = put_mid if put_mid > 0.01 else float(nearest_put.get("lastPrice", 0))
                if put_price > 0.01 and tte > 0.001:
                    iv_approx = put_price / (price * 0.4 * (tte ** 0.5))
                    if 0.01 < iv_approx < 5.0:
                        iv_pct = iv_approx * 100
                        if iv_min <= iv_pct <= iv_max:
                            result["iv"] = round(iv_pct, 1)
                            iv_found = True
                        else:
                            result["fail_reason"] = f"IV {iv_pct:.1f}% outside {iv_min}-{iv_max}% range"
                            return result
        except Exception:
            pass

        # Fallback to yfinance IV
        if not iv_found:
            for exp in exp_dates[:5]:
                try:
                    chain = stock.option_chain(exp)
                    if not chain.calls.empty:
                        chain.calls["dist"] = abs(chain.calls["strike"] - price)
                        nc = chain.calls.loc[chain.calls["dist"].idxmin()]
                        chain_iv = nc.get("impliedVolatility")
                        if chain_iv and float(chain_iv) > 0.001:
                            iv_pct = float(chain_iv) * 100
                            if iv_min <= iv_pct <= iv_max:
                                result["iv"] = round(iv_pct, 1)
                                iv_found = True
                                break
                except Exception:
                    pass

        if not iv_found:
            result["fail_reason"] = "No IV data available"
            return result

        # Margin check
        fin = stock.financials
        if fin is not None and not fin.empty:
            year = fin.iloc[:, 0]
            op_income = None
            revenue = None
            for k in ["Operating Income", "EBIT"]:
                if k in year.index:
                    op_income = float(year.loc[k])
                    break
            for k in ["Total Revenue", "Revenue"]:
                if k in year.index:
                    revenue = float(year.loc[k])
                    break
            if op_income is not None and revenue and revenue != 0:
                margin_pct = (op_income / revenue) * 100
                if margin_pct <= 0:
                    result["fail_reason"] = f"Margin {margin_pct:.1f}% (non-positive)"
                    return result
                result["margin"] = round(margin_pct, 2)
        else:
            result["fail_reason"] = "No financial data available"
            return result

        # CAGR from revenue history
        if fin.shape[1] >= 3:
            revenues = []
            for i in range(min(4, fin.shape[1])):
                col = fin.iloc[:, i]
                found = False
                for k in ["Total Revenue", "Revenue"]:
                    if k in col.index:
                        revenues.append(float(col.loc[k]))
                        found = True
                        break
                if not found:
                    revenues.append(None)
            revenues = [r for r in revenues if r]
            if len(revenues) >= 3 and revenues[-1] > 0 and revenues[0] > 0:
                n_periods = len(revenues) - 1
                cagr = ((revenues[0] / revenues[-1]) ** (1.0 / n_periods) - 1) * 100
                result["cagr"] = round(cagr, 2)

        # Business description / driver
        summary = info.get("longBusinessSummary") or ""
        if summary:
            sentences = [x.strip() for x in summary.replace("\n", " ").split(".")[:3] if x.strip()]
            result["driver"] = ". ".join(sentences)[:250]
        else:
            result["driver"] = ticker

        result["qualified"] = True
        return result

    except Exception as e:
        result["fail_reason"] = f"Error: {type(e).__name__}: {str(e)[:150]}"
        return result

LOADER_TIPS = [
    "The price filter runs first, so the slower options checks only run on stocks in your range.",
    "Implied volatility (IV) is the market's estimate of how much a stock may move.",
    "Weekly options give you more frequent expirations to work with.",
    "Many stocks are checked in parallel to keep the scan fast.",
]
_SPARKLE = ("<svg width='22' height='22' viewBox='0 0 24 24' fill='none' stroke='#ff6b3d' stroke-width='2' "
            "stroke-linecap='round' stroke-linejoin='round'><path d='M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z'/>"
            "<path d='M19 16l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7z'/></svg>")


def render_progress(ph, tiers, idx, tier_pct, detail, found=0):
    pct = max(0, min(100, int(100 * (idx + tier_pct / 100) / len(tiers))))
    tip = LOADER_TIPS[(pct // 10) % len(LOADER_TIPS)]
    cards = ""
    for i, k in enumerate(tiers):
        state = "Done" if i < idx else ("Scanning" if i == idx else "Queued")
        cards += (f"<div class='loader-card'><b>{state}</b>"
                  f"<span>{html.escape(TIERS[k]['label'])}</span></div>")
    cards += f"<div class='loader-card'><b class='pos'>{found}</b><span>Qualified so far</span></div>"
    ph.markdown(
        f"<div class='loader'><div class='loader-badge'>{_SPARKLE}</div>"
        f"<div class='loader-title'>Screening {html.escape(tiers[idx])}…</div>"
        f"<div class='loader-track'><div class='loader-fill' style='width:{pct}%'></div>"
        f"<span class='loader-pct'>{pct}%</span></div>"
        f"<div class='loader-detail'>{html.escape(detail)}</div>"
        f"<div class='loader-tip'><b>Did you know?</b>{html.escape(tip)}</div>"
        f"<div class='loader-cards'>{cards}</div></div>",
        unsafe_allow_html=True,
    )

# ── TIER SCAN (V2 exact pipeline: industry filter → batch price → deep) ──
def scan_tier(tier_name, tickers, sectors, name_map, price_min, price_max,
              iv_min, iv_max, min_vol, report):
    qualified = []
    failed = []
    report(0, f"Loaded {len(tickers)} tickers", 0)

    if not tickers:
        return [], []

    # 1. Industry/name pre-filter (V2 exact)
    passed = tier_name_filter(tickers, sectors, name_map)
    if not passed:
        return [], []

    # 2. Batch price filter (yf.download in groups of 300); occupies 0-20% of the bar
    priced = []
    for i in range(0, len(passed), 300):
        batch = passed[i:i + 300]
        report(20 * i / len(passed), f"Filtering {len(passed)} tickers by price", 0)
        try:
            data = yf.download(
                ",".join(batch),
                period="1d",
                interval="1d",
                progress=False,
                auto_adjust=False,
            )
            if data.empty:
                continue
            if "Close" in data.columns.levels[0]:
                closes = data["Close"].iloc[-1]
            else:
                closes = data.iloc[-1]
            for t in batch:
                if t in closes.index:
                    px = float(closes[t])
                    if pd.notna(px) and price_min <= px <= price_max:
                        priced.append((t, px))
        except Exception:
            continue

    if not priced:
        return [], []

    # 3. Deep screen in parallel (20-100% of the bar); results re-sorted to input order
    total_priced = len(priced)
    done = 0
    results = {}
    cache = _screen_cache()

    def screen_cached(t, px):
        key = (t, round(px, 2), iv_min, iv_max, min_vol)
        hit = cache.get(key)
        if hit and time.time() - hit[0] < SCREEN_CACHE_TTL:
            return dict(hit[1])
        r = deep_screen(t, px, iv_min, iv_max, min_vol)
        # Don't cache Yahoo throttling/errors, so they are retried next run
        if r["qualified"] or not any(s in r["fail_reason"] for s in ("Yahoo", "Error:", "No data")):
            cache[key] = (time.time(), dict(r))
        return r

    with ThreadPoolExecutor(max_workers=DEEP_SCREEN_WORKERS) as pool:
        futures = {pool.submit(screen_cached, t, px): i
                   for i, (t, px) in enumerate(priced)}
        for fut in as_completed(futures):
            result = fut.result()
            result["tier"] = tier_name
            results[futures[fut]] = result
            done += 1
            n_q = sum(1 for r in results.values() if r["qualified"])
            report(20 + 80 * done / total_priced,
                   f"Deep screening {done} of {total_priced} candidates", n_q)
    for i in sorted(results):
        (qualified if results[i]["qualified"] else failed).append(results[i])

    return qualified, failed

# ═══════════════════════════════════════════════════════════════════════
# STREAMLIT UI
# ═══════════════════════════════════════════════════════════════════════

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html,body,[class*="css"],.stApp{font-family:'Inter',sans-serif}
.stApp{background:#f6f5f3;color:#1f2328}
.block-container{max-width:860px;padding-top:2rem}
header[data-testid="stHeader"]{background:transparent}
.main-title{font-size:1.9rem;font-weight:700;letter-spacing:-0.02em;color:#1f2328}
.subtitle{color:#6b7280;margin:0.2rem 0 1.5rem;font-size:0.95rem}
.section-label{color:#6b7280;font-weight:600;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.1em;margin:1.4rem 0 0.6rem}
.chip-row{display:flex;flex-wrap:wrap;gap:0.5rem}
.chip{background:#fff;border:1px solid #e6e3de;border-radius:999px;padding:0.35rem 0.85rem;font-size:0.82rem;color:#4b5563}
.chip b{color:#1f2328;font-weight:600}
.chip.ok{border-color:#bfe3cf;background:#e9f6ee}
.chip.no{border-color:#f1c9c9;background:#fbeeee}
.card{background:#fff;border:1px solid #e6e3de;border-radius:12px;padding:1.1rem 1.25rem;margin-bottom:0.9rem;box-shadow:0 1px 2px rgba(0,0,0,.04);transition:box-shadow .15s}
.card:hover{box-shadow:0 4px 14px rgba(0,0,0,.08)}
.card-head{display:flex;justify-content:space-between;align-items:flex-start;gap:1rem}
.card-name{font-size:1.05rem;font-weight:600;color:#1f2328}
.card-sub{font-size:0.8rem;color:#6b7280;margin-top:0.15rem}
.card-price{font-size:1.35rem;font-weight:700;color:#1f2328;text-align:right}
.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:0.6rem;margin-top:0.9rem}
.metric{background:#f6f5f3;border-radius:8px;padding:0.55rem 0.7rem}
.metric span{display:block;font-size:0.68rem;color:#6b7280;text-transform:uppercase;letter-spacing:0.06em}
.metric b{font-size:0.98rem;color:#1f2328;font-weight:600}
.pos{color:#1f9d63!important}.neg{color:#d64545!important}
.tier-tag{display:inline-block;padding:0.1rem 0.55rem;border-radius:999px;font-size:0.68rem;font-weight:600;color:#fff;margin-left:0.5rem;vertical-align:middle}
.driver{margin-top:0.8rem;font-size:0.82rem;color:#6b7280;line-height:1.5}
.stButton>button{border-radius:8px;border:1px solid #e6e3de;background:#fff;color:#1f2328;font-weight:500}
.stButton>button:hover{border-color:#ff6b3d;color:#ff6b3d}
.stButton>button[kind="primary"]{background:#ff6b3d;border-color:#ff6b3d;color:#fff;font-weight:600}
.stButton>button[kind="primary"]:hover{background:#e85a2d;color:#fff}
div[data-testid="stStatusWidget"]{display:none!important}
@media(max-width:640px){.metrics{grid-template-columns:repeat(2,1fr)}}
section[data-testid="stSidebar"]{background:#fff;border-right:1px solid #e6e3de}
section[data-testid="stSidebar"] .section-label{margin-top:0.4rem}
.side-brand{font-weight:700;font-size:1.1rem;color:#1f2328;margin-bottom:0.5rem}
.side-brand i{display:inline-block;width:10px;height:10px;border-radius:3px;background:#ff6b3d;margin-right:8px}
.loader{padding:3rem 0.5rem 1.5rem;margin:0.8rem 0;text-align:center}
.loader-badge{width:46px;height:46px;margin:0 auto 1rem;border-radius:50%;background:#fff0ea;display:flex;align-items:center;justify-content:center;animation:pulse 1.6s ease-in-out infinite}
@keyframes pulse{50%{transform:scale(1.1)}}
.loader-title{font-size:1.05rem;font-weight:600;color:#1f2328;margin-bottom:1rem}
.loader-track{position:relative;height:18px;max-width:520px;margin:0 auto;background:#ffe9e1;border-radius:999px;overflow:hidden}
.loader-fill{height:100%;background:#ff6b3d;border-radius:999px;transition:width .3s ease}
.loader-pct{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:0.68rem;font-weight:600;color:#1f2328}
.loader-detail{margin-top:0.9rem;font-size:0.82rem;color:#6b7280}
.loader-tip{margin:1.6rem auto 0;max-width:420px;font-size:0.76rem;color:#6b7280;line-height:1.5}
.loader-tip b{display:block;color:#1f2328;font-weight:600;margin-bottom:0.1rem}
.loader-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:0.7rem;margin-top:2.2rem;text-align:left}
.loader-card{background:#fff;border:1px solid #e6e3de;border-radius:10px;padding:0.8rem 0.9rem}
.loader-card b{display:block;font-size:1.2rem;font-weight:700;color:#1f2328}
.loader-card span{font-size:0.76rem;color:#6b7280}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">Francine Screener</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Options-liquid stocks across four market tiers, no industry exclusions.</div>', unsafe_allow_html=True)

# Criteria display
st.markdown('<div class="section-label">Screening criteria</div>', unsafe_allow_html=True)
st.markdown("""
<div class="chip-row">
<span class="chip ok"><b>All industries</b></span>
<span class="chip no"><b>Blocked:</b> China, Russia, Latin America</span>
<span class="chip"><b>Weekly options</b> with volume</span>
<span class="chip"><b>IV</b> target ±10</span>
<span class="chip"><b>Volume</b> ≥ 2M</span>
<span class="chip"><b>Margin</b> &gt; 0%</span>
</div>
""", unsafe_allow_html=True)

# Tier selection
tier_keys = list(TIERS.keys())
if "_tier_init" not in st.session_state:
    for k in tier_keys:
        st.session_state[f"tc_{k}"] = (k == "S&P 500")
    st.session_state._tier_init = True

# Preset handler
preset = st.session_state.get("_preset", None)
if preset:
    for k in tier_keys:
        if preset == "t1":
            v = (k == "S&P 500")
        elif preset == "t13":
            v = (k in ("S&P 500", "S&P 400", "S&P 600"))
        elif preset == "all":
            v = True
        elif preset == "none":
            v = False
        st.session_state[f"tc_{k}"] = v
        st.session_state[f"cb_{k}"] = v  # sync widget key so checkbox renders correctly
    del st.session_state._preset
    st.rerun()

with st.sidebar:
    st.markdown('<div class="side-brand"><i></i>Francine</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-label">Tier selection</div>', unsafe_allow_html=True)
    pc = st.columns(2)
    if pc[0].button("Tier 1", use_container_width=True):
        st.session_state._preset = "t1"; st.rerun()
    if pc[1].button("Tiers 1-3", use_container_width=True):
        st.session_state._preset = "t13"; st.rerun()
    if pc[0].button("All 4", use_container_width=True):
        st.session_state._preset = "all"; st.rerun()
    if pc[1].button("Clear", use_container_width=True):
        st.session_state._preset = "none"; st.rerun()

    for k in tier_keys:
        ck = f"tc_{k}"
        if ck not in st.session_state:
            st.session_state[ck] = (k == "S&P 500")
        st.checkbox(f"{TIERS[k]['label']} — {TIERS[k]['desc']}",
                    value=st.session_state[ck], key=f"cb_{k}")
        st.session_state[ck] = st.session_state[f"cb_{k}"]

    st.markdown('<div class="section-label">Parameters</div>', unsafe_allow_html=True)
    pr = st.columns(2)
    price_min = pr[0].number_input("From $", min_value=0.0, value=5.0, step=5.0)
    price_max = pr[1].number_input("To $", min_value=0.0, value=20.0, step=5.0)
    iv_target = st.number_input("IV target %", min_value=0.0, value=30.0, step=5.0)
    min_vol = st.number_input("Min volume", min_value=0, value=1000000, step=500000)

    iv_min = max(0, iv_target - 10)
    iv_max = iv_target + 10
    st.caption(f"IV range: {iv_min:.0f}–{iv_max:.0f}%")

    run = st.button("Run screen", type="primary", use_container_width=True)

selected = [k for k in tier_keys if st.session_state.get(f"tc_{k}", False)]

# ── SCREENING ──────────────────────────────────────────────────────────
if run:
    if price_min <= 0 or price_max <= 0:
        st.error("Enter valid price range.")
    elif price_min >= price_max:
        st.error("'To:' must be greater than 'From:'.")
    elif not selected:
        st.error("Select at least one tier.")
    else:
        all_qualified = []
        all_failed = []
        loader_ph = st.empty()

        for tier_idx, tier_name in enumerate(selected):
            render_progress(loader_ph, selected, tier_idx, 0, "Loading tickers", len(all_qualified))

            sectors = {}
            name_map = {}

            if tier_name == "Rest":
                prev = []
                for k in ["S&P 500", "S&P 400", "S&P 600"]:
                    if k in selected[:selected.index(tier_name)]:
                        tk, _ = load_index(k)
                        prev.extend(tk)
                tickers = get_rest_tickers(set(prev))
                if not tickers:
                    st.info("No stocks loaded for Rest of Market.")
                    continue
            else:
                tickers, sectors = load_index(tier_name)
                if not tickers:
                    st.warning(f"Could not load {tier_name}.")
                    continue

            def report(pct, detail, n_q, _i=tier_idx, _base=len(all_qualified)):
                render_progress(loader_ph, selected, _i, pct, detail, _base + n_q)

            q, f = scan_tier(tier_name, tickers, sectors, name_map,
                             price_min, price_max, iv_min, iv_max, min_vol, report)
            all_qualified.extend(q)
            all_failed.extend(f)

        loader_ph.empty()
        st.session_state.results = (all_qualified, all_failed)


def build_pdf(rows):
    from fpdf import FPDF

    def clean(s):
        return str(s).encode("latin-1", "replace").decode("latin-1")

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, f"Francine Screener Results ({len(rows)} qualified)",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=9)
    for q in rows:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, clean(f"{q.get('ticker','')} - {q.get('company_name','')}  ${q.get('price',0):.2f}"),
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", size=9)
        cagr = q.get("cagr")
        pdf.multi_cell(0, 5, clean(
            f"Tier: {q.get('tier','')} | {q.get('sector','N/A')} / {q.get('industry','N/A')}\n"
            f"IV: {q.get('iv',0):.1f}% | Avg volume: {(q.get('avg_volume') or 0):,} | "
            f"Margin: {(q.get('margin') or 0):.1f}% | Rev CAGR: {'n/a' if cagr is None else f'{cagr:+.1f}%'}\n"
            f"{q.get('driver','')}"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
    return bytes(pdf.output())


def render_results(all_qualified, all_failed):
        st.markdown("---")
        st.markdown("## Results: " + str(len(all_qualified)) + " qualified")

        if all_qualified:
            for idx, q in enumerate(all_qualified, 1):
                tn = q.get("tier", "")
                tc = TIERS.get(tn, {}).get("color", "#555")
                cagr = q.get("cagr")
                cagr_html = (f"<b class='{'pos' if cagr >= 0 else 'neg'}'>{cagr:+.1f}%</b>"
                             if cagr is not None else "<b>—</b>")
                name = html.escape(q.get("company_name", ""))
                st.markdown(
                    f"<div class='card'><div class='card-head'><div>"
                    f"<div class='card-name'>{name} · {html.escape(q['ticker'])}"
                    f"<span class='tier-tag' style='background:{tc}'>{html.escape(tn)}</span></div>"
                    f"<div class='card-sub'>{html.escape(q.get('sector','N/A'))} / {html.escape(q.get('industry','N/A'))}</div></div>"
                    f"<div class='card-price'>${q['price']:.2f}</div></div>"
                    f"<div class='metrics'>"
                    f"<div class='metric'><span>IV</span><b>{q['iv']:.1f}%</b></div>"
                    f"<div class='metric'><span>Avg volume</span><b>{(q.get('avg_volume') or 0):,}</b></div>"
                    f"<div class='metric'><span>Margin</span><b>{(q.get('margin') or 0):.1f}%</b></div>"
                    f"<div class='metric'><span>Rev CAGR</span>{cagr_html}</div></div>"
                    f"<div class='driver'>{html.escape(q.get('driver',''))}</div></div>",
                    unsafe_allow_html=True,
                )

            # ── CSV download ──
            csv_lines = []
            csv_lines.append("ticker,company_name,price,iv,avg_volume,margin,cagr,sector,industry,tier,options_liquid,driver")
            for q in all_qualified:
                row = (
                    q.get("ticker",""),
                    q.get("company_name","").replace(","," "),
                    q.get("price",0),
                    q.get("iv",0),
                    q.get("avg_volume") or 0,
                    q.get("margin") or 0,
                    q.get("cagr") or 0,
                    q.get("sector","").replace(","," "),
                    q.get("industry","").replace(","," "),
                    q.get("tier",""),
                    "Yes" if q.get("options_liquid") else "No",
                    q.get("driver","").replace(","," "),
                )
                csv_lines.append(",".join(str(v) for v in row))
            csv_data = "\n".join(csv_lines)

            with st.popover("📥 Download Results"):
                st.download_button(
                    "CSV",
                    data=csv_data,
                    file_name="francine_screener_v3_results.csv",
                    mime="text/csv",
                    key="dl_csv",
                    use_container_width=True,
                )
                st.download_button(
                    "PDF",
                    data=build_pdf(all_qualified),
                    file_name="francine_screener_v3_results.pdf",
                    mime="application/pdf",
                    key="dl_pdf",
                    use_container_width=True,
                )
        else:
            st.warning("No qualified companies found.")

        if all_failed:
            with st.expander(f"📊 Failure Summary ({len(all_failed)} total)"):
                reasons = Counter()
                for r in all_failed[:200]:
                    reasons[r.get("fail_reason", "Unknown")[:200]] += 1
                for reason, count in reasons.most_common(10):
                    st.markdown(f"- **{reason}**: {count}")


if "results" in st.session_state:
    render_results(*st.session_state.results)