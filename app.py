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
import os
import sys
from datetime import datetime, timedelta
from collections import Counter

st.set_page_config(page_title="Francine Screener V3", page_icon="📊", layout="centered", initial_sidebar_state="collapsed")

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
DEEP_SCREEN_DELAY = 0.8

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

        # Options liquidity check (need 2+ weeklies with volume)
        exp_dates = stock.options
        if not exp_dates or len(exp_dates) < 2:
            result["fail_reason"] = "No weekly options chain"
            return result

        weeks_with_volume = 0
        for exp in exp_dates[:10]:
            try:
                chain = stock.option_chain(exp)
                if (chain.calls["volume"].sum() + chain.puts["volume"].sum()) > 0:
                    weeks_with_volume += 1
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

        # Volume check
        avg_vol = int(info.get("averageVolume") or info.get("averageDailyVolume10Day") or 0)
        result["avg_volume"] = avg_vol
        result["volume"] = avg_vol
        if avg_vol < min_vol:
            result["fail_reason"] = f"Avg volume {avg_vol:,} < {min_vol:,}"
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
        result["fail_reason"] = f"Error: {str(e)[:100]}"
        return result

# ── TIER SCAN (V2 exact pipeline: industry filter → batch price → deep) ──
def scan_tier(tier_name, tickers, sectors, name_map, price_min, price_max,
              iv_min, iv_max, min_vol):
    qualified = []
    failed = []
    status_placeholder = st.empty()
    progress_placeholder = st.progress(0.0, text=f"Loading {tier_name}...")

    if not tickers:
        return [], []

    # 1. Industry/name pre-filter (V2 exact)
    passed = tier_name_filter(tickers, sectors, name_map)
    if not passed:
        return [], []

    # 2. Batch price filter (yf.download in groups of 300)
    priced = []
    for i in range(0, len(passed), 300):
        batch = passed[i:i + 300]
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

    status_placeholder.text(f"Deep screening {len(priced)} candidates in {tier_name}...")

    # 3. Deep screen (sequential with 0.8s delay)
    total_priced = len(priced)
    for i, (t, px) in enumerate(priced):
        result = deep_screen(t, px, iv_min, iv_max, min_vol)
        result["tier"] = tier_name  # tag result with tier
        if result["qualified"]:
            qualified.append(result)
        else:
            failed.append(result)

        if i < total_priced - 1:
            time.sleep(DEEP_SCREEN_DELAY)

        if i % max(1, total_priced // 10) == 0:
            progress_placeholder.progress(
                (i + 1) / total_priced,
                text=f"{tier_name}: {i+1}/{total_priced} — {len(qualified)} qualified",
            )

    progress_placeholder.progress(
        1.0,
        text=f"{tier_name}: Done — {len(qualified)} qualified",
    )
    return qualified, failed

# ═══════════════════════════════════════════════════════════════════════
# STREAMLIT UI
# ═══════════════════════════════════════════════════════════════════════

st.markdown("""
<style>
.main-title{font-size:1.8rem;font-weight:700}
.subtitle{color:#888;margin-bottom:0.5rem}
.section-label{color:#aaa;font-weight:600;font-size:0.85rem;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:0.3rem}
.criterion{background:#262626;padding:0.4rem 0.8rem;border-radius:6px;border-left:3px solid #555;font-size:0.85rem;color:#ddd;margin-bottom:0.3rem}
.criterion strong{color:#fff}
.tag-allow{display:inline-block;background:#1b5e20;color:#c8e6c9;padding:0 0.5rem;border-radius:4px;font-size:0.75rem;font-weight:600;margin-right:0.3rem}
.tag-block{display:inline-block;background:#b71c1c;color:#ffcdd2;padding:0 0.5rem;border-radius:4px;font-size:0.75rem;font-weight:600;margin-right:0.3rem}
.tag-req{display:inline-block;background:#1a237e;color:#c5cae9;padding:0 0.5rem;border-radius:4px;font-size:0.75rem;font-weight:600;margin-right:0.3rem}
.pass-badge{color:#4caf50;font-weight:600}
.fail-badge{color:#f44336;font-weight:600}
.qualified-badge{display:inline-block;background:#1b5e20;color:#fff;padding:0.15rem 0.6rem;border-radius:12px;font-size:0.8rem;font-weight:600}
div[data-testid="stStatusWidget"]{display:none!important}
.tier-tag{display:inline-block;padding:0.1rem 0.5rem;border-radius:4px;font-size:0.7rem;font-weight:600;color:#fff;margin-left:0.3rem}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">📊 FRANCINE SCREENER V3</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">V2 screening logic | 4-tier scanning | NO industry exclusions</div>', unsafe_allow_html=True)

# Criteria display
st.markdown('<div class="section-label">Screening Criteria</div>', unsafe_allow_html=True)
st.markdown("""
<div class="criterion" style="border-left-color:#42a5f5"><span class="tag-allow">ALLOW</span> <strong>All industries — no exclusions</strong></div>
<div class="criterion" style="border-left-color:#66bb6a"><span class="tag-block">BLOCK</span> <strong>China, Russia, Latin America</strong></div>
<div class="criterion" style="border-left-color:#f9a825"><span class="tag-req">LIQUID</span> <strong>Weekly options</strong> with trading volume</div>
<div class="criterion" style="border-left-color:#ab47bc"><span class="tag-req">IV RANGE</span> <strong>28–48%</strong> &middot; <strong>Volume</strong> &ge;2M &middot; <strong>Margin</strong> &gt;0%</div>
""", unsafe_allow_html=True)

# Tier selection
st.markdown('<div class="section-label">Tier Selection</div>', unsafe_allow_html=True)
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

cols = st.columns(4)
with cols[0]:
    if st.button("📋 Tier 1", use_container_width=True):
        st.session_state._preset = "t1"; st.rerun()
with cols[1]:
    if st.button("📋 Tiers 1-3", use_container_width=True):
        st.session_state._preset = "t13"; st.rerun()
with cols[2]:
    if st.button("🌐 All 4", use_container_width=True):
        st.session_state._preset = "all"; st.rerun()
with cols[3]:
    if st.button("🗑️ Clear", use_container_width=True):
        st.session_state._preset = "none"; st.rerun()

for k in tier_keys:
    ck = f"tc_{k}"
    if ck not in st.session_state:
        st.session_state[ck] = (k == "S&P 500")
    st.checkbox(f"{TIERS[k]['label']} — {TIERS[k]['desc']}",
                value=st.session_state[ck], key=f"cb_{k}")
    st.session_state[ck] = st.session_state[f"cb_{k}"]

selected = [k for k in tier_keys if st.session_state.get(f"tc_{k}", False)]

# Price + IV + Volume inputs
st.markdown("---")
st.markdown('<div class="section-label">Parameters</div>', unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)
with c1:
    price_min = st.number_input("From $", min_value=0.0, value=10.0, step=5.0)
with c2:
    price_max = st.number_input("To $", min_value=0.0, value=50.0, step=5.0)
with c3:
    iv_target = st.number_input("IV target %", min_value=0.0, value=35.0, step=5.0)
with c4:
    min_vol = st.number_input("Min Vol", min_value=0, value=2000000, step=500000)

iv_min = max(0, iv_target - 10)
iv_max = iv_target + 10

st.markdown(f"<small>IV range: {iv_min:.0f}–{iv_max:.0f}% | Default: 28–48%</small>",
            unsafe_allow_html=True)

run = st.button("🚀 RUN SCREEN", type="primary", use_container_width=True)

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

        for tier_name in selected:
            st.markdown(f"### 🔍 {TIERS[tier_name]['label']}")

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
                st.caption(f"Loaded {len(tickers)} tickers from NASDAQ/NYSE")
            else:
                tickers, sectors = load_index(tier_name)
                if not tickers:
                    st.warning(f"Could not load {tier_name}.")
                    continue
                st.caption(f"Loaded {len(tickers)} tickers from Wikipedia")

            q, f = scan_tier(tier_name, tickers, sectors, name_map,
                             price_min, price_max, iv_min, iv_max, min_vol)
            all_qualified.extend(q)
            all_failed.extend(f)

        # ── RESULTS ────────────────────────────────────────────────────
        st.markdown("---")
        st.markdown(f"## ✅ Results: {len(all_qualified)} qualified")

        if all_qualified:
            for idx, q in enumerate(all_qualified, 1):
                tn = q.get("tier", "")
                tc = TIERS.get(tn, {}).get("color", "#555")
                with st.container(border=True):
                    st.markdown(
                        f"### {idx}. {q['company_name']} ({q['ticker']})"
                        f"<span class='tier-tag' style='background:{tc}'>{tn}</span>",
                        unsafe_allow_html=True,
                    )
                    cc1, cc2 = st.columns([1, 2])
                    with cc1:
                        st.markdown(
                            f"**Sector:** {q.get('sector','N/A')} / {q.get('industry','N/A')}")
                        st.markdown(
                            f"**Options:** {'✅ Liquid' if q.get('options_liquid') else '❌'}")
                    with cc2:
                        st.markdown(f"**Price:** ${q['price']:.2f}")
                        st.markdown(f"**IV:** {q['iv']:.1f}%")
                        st.markdown(f"**Volume:** {(q.get('avg_volume') or 0):,}")
                        st.markdown(f"**Margin:** {(q.get('margin') or 0):.1f}%")
                        if q.get("cagr"):
                            st.markdown(f"**CAGR:** {q['cagr']:+.1f}%")
                    st.markdown(
                        "<span class='qualified-badge'>V3 QUALIFIED</span>",
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

            st.download_button(
                "📥 Download Results as CSV",
                data=csv_data,
                file_name="francine_screener_v3_results.csv",
                mime="text/csv",
            )
        else:
            st.warning("No qualified companies found.")

        if all_failed:
            with st.expander(f"📊 Failure Summary ({len(all_failed)} total)"):
                reasons = Counter()
                for r in all_failed[:200]:
                    reasons[r.get("fail_reason", "Unknown")[:50]] += 1
                for reason, count in reasons.most_common(10):
                    st.markdown(f"- **{reason}**: {count}")