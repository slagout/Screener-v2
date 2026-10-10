"""
FRANCINE SCREENER V3
====================
S&P 500 screener. Fundamentals, prices and company data come from Financial
Modeling Prep (data_sources/fmp.py); weekly options and IV come from yfinance
(data_sources/options.py) because FMP has no options data.

Filters (README "What it checks"): industry exclusions, country allowlist, price
range, >=25% below 52-week high, IV floor, Altman-Z > 3.0, weekly options required.
"""
import csv
import html
import io
import re
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import pandas as pd
import streamlit as st

from data_sources import constituents, fmp, options

st.set_page_config(page_title="Francine Screener V3", page_icon="📊", layout="wide",
                   initial_sidebar_state="expanded")

# ── V3 SCREEN RULES — keep in sync with README "What it checks" ─────────
# Banking, insurance, lending and financial services are blocked. Pharma, tobacco
# and cannabis are deliberately ALLOWED (that is the V2 -> V3 difference); do not
# add them back. Matched as word prefixes against sector + industry text.
BLOCKED_INDUSTRIES = [
    "bank", "insurance", "insurer", "reinsurance",
    "lending", "consumer finance", "mortgage", "credit services",
    "financial services", "financials", "financial -", "diversified financial",
    "asset management", "capital markets",
]

# README: US, Canada, Europe, UK, Australia/NZ, Japan, South Korea (ISO-3166 alpha-2,
# as returned by FMP's profile "country" field).
ALLOWED_COUNTRIES_BY_REGION = {
    "United States": {"US"},
    "Canada": {"CA"},
    "United Kingdom": {"GB"},
    "Europe": {
        "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU",
        "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE",
        "CH", "NO", "IS", "LI",
    },
    "Australia/NZ": {"AU", "NZ"},
    "Japan": {"JP"},
    "South Korea": {"KR"},
}
ALLOWED_COUNTRIES = set().union(*ALLOWED_COUNTRIES_BY_REGION.values())
_COUNTRY_ALIASES = {"UK": "GB"}

MIN_BELOW_52W_HIGH_PCT = 25.0
MIN_ALTMAN_Z = 3.0
DEFAULT_MIN_IV = 30.0
SCREEN_WORKERS = 4

STAGES = ["Price & 52-week high", "Profile: industry & country", "Weekly options & IV", "Altman-Z & financials"]


def blocked_industry(*texts):
    blob = " ".join(t for t in texts if t).lower()
    for kw in BLOCKED_INDUSTRIES:
        if re.search(rf"\b{re.escape(kw)}", blob):
            return kw
    return None


def country_allowed(code):
    c = (code or "").strip().upper()
    return _COUNTRY_ALIASES.get(c, c) in ALLOWED_COUNTRIES


def altman_z(income, balance, market_cap):
    """Classic Altman Z: 1.2·WC/TA + 1.4·RE/TA + 3.3·EBIT/TA + 0.6·MktCap/TL + 1.0·Rev/TA."""
    try:
        ta = float(balance["totalAssets"])
        tl = float(balance["totalLiabilities"])
        wc = float(balance["totalCurrentAssets"]) - float(balance["totalCurrentLiabilities"])
        re_ = float(balance["retainedEarnings"])
        ebit = income.get("ebit")
        ebit = float(income["operatingIncome"] if ebit is None else ebit)
        rev = float(income["revenue"])
        mc = float(market_cap)
    except (KeyError, TypeError, ValueError):
        return None
    if ta <= 0 or tl <= 0 or mc <= 0:
        return None
    return 1.2 * wc / ta + 1.4 * re_ / ta + 3.3 * ebit / ta + 0.6 * mc / tl + 1.0 * rev / ta


def _ts(epoch):
    return datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M") if epoch else "n/a"


def screen_ticker(sym, name, gics_text, price_min, price_max, min_iv, stop):
    """Cheapest check first so scarce FMP calls are only spent on survivors."""
    r = {"ticker": sym, "company_name": name, "qualified": False, "fail_reason": "",
         "fail_group": "", "stage": 0, "sector": "", "industry": "", "hq": ""}

    def fail(group, reason):
        r["fail_group"], r["fail_reason"] = group, reason
        return r

    if stop.is_set():
        return fail("Skipped (FMP unavailable)", "Skipped: FMP budget/auth problem earlier in this run")
    try:
        # 1. Quote: price range + 52-week high
        q = fmp.get_quote(sym)
        price, year_high = q.get("price"), q.get("yearHigh")
        if not price or not year_high:
            return fail("UNKNOWN (data missing)", "UNKNOWN: quote has no price/52-week high")
        r.update(price=float(price), year_high=float(year_high), quote_at=q["_fetched_at"])
        if not price_min <= price <= price_max:
            return fail("Price outside range", f"Price ${price:.2f} outside ${price_min:.0f}-${price_max:.0f}")
        r["pct_below_high"] = (year_high - price) / year_high * 100
        if r["pct_below_high"] < MIN_BELOW_52W_HIGH_PCT:
            return fail("Not 25% below 52-week high",
                        f"Only {r['pct_below_high']:.1f}% below 52-week high (need {MIN_BELOW_52W_HIGH_PCT:.0f}%)")
        r["stage"] = 1

        # 2. Profile: industry exclusions + geography allowlist
        p = fmp.get_profile(sym)
        r.update(company_name=p.get("companyName") or name, sector=p.get("sector") or "N/A",
                 industry=p.get("industry") or "N/A", country=p.get("country") or "",
                 hq=", ".join(x for x in (p.get("city"), p.get("country")) if x),
                 exchange=p.get("exchange") or "", profile_at=p["_fetched_at"])
        hit = blocked_industry(p.get("sector"), p.get("industry"))
        if hit:
            return fail("Blocked industry", f"Blocked industry: {r['sector']} / {r['industry']}")
        if not r["country"]:
            return fail("UNKNOWN (data missing)", "UNKNOWN: profile has no country")
        if not country_allowed(r["country"]):
            return fail("Country not allowed", f"Country {r['country']} not on allowlist")
        r["stage"] = 2

        # 3. Options (yfinance): weekly required, IV floor
        o = options.check_options(sym, float(price))
        if o.status == "unknown":
            return fail("UNKNOWN (data fetch)", o.reason)
        if not o.has_weekly:
            return fail("No weekly options", o.reason)
        if o.iv is None:
            return fail("UNKNOWN (data missing)", "UNKNOWN: no IV could be computed")
        if o.iv < min_iv:
            return fail("IV below floor", f"IV {o.iv:.1f}% below {min_iv:.0f}% floor")
        r.update(iv=o.iv, weekly_exp=o.weekly_exp, options_at=o.fetched_at)
        r["stage"] = 3

        # 4. Financials: Altman-Z, LT debt / FCF
        inc, bal, cf = fmp.get_income(sym), fmp.get_balance(sym), fmp.get_cashflow(sym)
        z = altman_z(inc, bal, q.get("marketCap"))
        if z is None:
            return fail("UNKNOWN (data missing)", "UNKNOWN: statements missing fields for Altman-Z")
        r["altman_z"] = z
        if z <= MIN_ALTMAN_Z:
            return fail("Altman-Z not above 3.0", f"Altman-Z {z:.2f} (need > {MIN_ALTMAN_Z})")
        lt_debt, fcf = bal.get("longTermDebt"), cf.get("freeCashFlow")
        r.update(lt_debt=lt_debt, fcf=fcf, fin_date=inc.get("date"), fin_at=inc["_fetched_at"],
                 lt_debt_fcf=(lt_debt / fcf if lt_debt is not None and fcf and fcf > 0 else None))
        r["stage"] = 4
        r["qualified"] = True
        return r
    except fmp.FMPPlanRestricted:
        return fail("Not covered by FMP plan", "Not covered by your FMP plan (free tier covers ~87 symbols)")
    except (fmp.FMPBudgetExhausted, fmp.FMPRateLimited, fmp.FMPAuthError) as exc:
        stop.set()
        return fail("Skipped (FMP unavailable)", f"Stopped: {exc}")
    except fmp.FMPDataError as exc:
        return fail("UNKNOWN (data fetch)", f"UNKNOWN: FMP fetch failed ({exc})")
    except Exception as exc:
        return fail("UNKNOWN (data fetch)", f"UNKNOWN: {type(exc).__name__}")


def render_progress(ph, done, total, funnel, found, detail):
    pct = int(100 * done / total) if total else 0
    steps = ""
    for i, label in enumerate(STAGES):
        state = "done" if total and done == total else ("active" if funnel[i] else "")
        steps += (f"<div class='loader-step {state}'><span class='loader-dot'>{i + 1}</span>"
                  f"{html.escape(label)} &middot; {funnel[i]} passed</div>")
    ph.markdown(
        f"<div class='loader'><div class='loader-icon'></div>"
        f"<div class='loader-title'>Screening the S&amp;P 500</div>"
        f"<div class='loader-track'><div class='loader-fill' style='width:{pct}%'></div>"
        f"<span class='loader-pct'>{pct}%</span></div>"
        f"<div class='loader-detail'>{html.escape(detail)}</div>"
        f"<div class='loader-steps'>{steps}</div>"
        f"<div class='loader-found'><b>{found}</b> qualified so far</div></div>",
        unsafe_allow_html=True,
    )


def run_screen(tickers, names, gics, price_min, price_max, min_iv, ph):
    qualified, failed = [], []
    stop = threading.Event()
    funnel = [0] * len(STAGES)
    todo = []
    for t in tickers:
        hit = blocked_industry(gics.get(t))
        if hit:
            failed.append({"ticker": t, "company_name": names.get(t, t), "stage": 0,
                           "fail_group": "Blocked industry",
                           "fail_reason": f"Blocked industry: {gics.get(t)}"})
        else:
            todo.append(t)

    done = 0
    results = {}
    render_progress(ph, 0, len(todo), funnel, 0, f"{len(tickers) - len(todo)} blocked by industry before any API call")
    with ThreadPoolExecutor(max_workers=SCREEN_WORKERS) as pool:
        futures = {pool.submit(screen_ticker, t, names.get(t, t), gics.get(t, ""),
                               price_min, price_max, min_iv, stop): i for i, t in enumerate(todo)}
        for fut in as_completed(futures):
            res = fut.result()
            results[futures[fut]] = res
            done += 1
            for s in range(res["stage"]):
                funnel[s] += 1
            n_q = sum(1 for x in results.values() if x["qualified"])
            render_progress(ph, done, len(todo), funnel, n_q, f"Checked {done} of {len(todo)} tickers")
    for i in sorted(results):
        (qualified if results[i]["qualified"] else failed).append(results[i])
    return qualified, failed


def fmt_money(n):
    if n is None:
        return "n/a"
    sign = "-" if n < 0 else ""
    n = abs(float(n))
    for div, suf in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if n >= div:
            return f"{sign}${n / div:.2f}{suf}"
    return f"{sign}${n:,.0f}"


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
.driver{margin-top:0.8rem;font-size:0.8rem;color:#6b7280;line-height:1.5}
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
.loader{background:#fff;border:1px solid #e6e3de;border-radius:16px;padding:2rem 1.5rem;margin:0.8rem 0;text-align:center;box-shadow:0 1px 2px rgba(0,0,0,.04)}
.loader-icon{width:36px;height:36px;margin:0 auto 0.9rem;border-radius:50%;border:3px solid #ffe3d9;border-top-color:#ff6b3d;animation:spin .9s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.loader-title{font-size:1.05rem;font-weight:600;color:#1f2328;margin-bottom:1rem}
.loader-track{position:relative;height:18px;max-width:520px;margin:0 auto;background:#ffe9e1;border-radius:999px;overflow:hidden}
.loader-fill{height:100%;background:#ff6b3d;border-radius:999px;transition:width .3s ease}
.loader-pct{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:0.68rem;font-weight:600;color:#1f2328}
.loader-detail{margin-top:0.9rem;font-size:0.82rem;color:#6b7280}
.loader-found{margin-top:0.2rem;font-size:0.8rem;color:#6b7280}
.loader-found b{color:#1f9d63}
.loader-steps{display:flex;flex-direction:column;gap:0.4rem;max-width:340px;margin:1.1rem auto 0.6rem;text-align:left}
.loader-step{display:flex;align-items:center;gap:0.6rem;font-size:0.82rem;color:#9ca3af}
.loader-step.active{color:#1f2328;font-weight:600}
.loader-step.done{color:#1f9d63}
.loader-dot{width:20px;height:20px;border-radius:50%;border:1.5px solid currentColor;display:inline-flex;align-items:center;justify-content:center;font-size:0.66rem}
.loader-step.active .loader-dot{background:#ff6b3d;border-color:#ff6b3d;color:#fff}
.loader-step.done .loader-dot{background:#e9f6ee}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">Francine Screener</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">S&amp;P 500 stocks with weekly options, deep drawdown and strong balance sheets.</div>', unsafe_allow_html=True)

st.markdown('<div class="section-label">Screening criteria</div>', unsafe_allow_html=True)
st.markdown(f"""
<div class="chip-row">
<span class="chip"><b>Universe</b> S&amp;P 500</span>
<span class="chip no"><b>Blocked:</b> banking, insurance, lending, financial services</span>
<span class="chip ok"><b>Allowed:</b> pharma, tobacco, cannabis</span>
<span class="chip"><b>Regions:</b> US, Canada, Europe, UK, Australia/NZ, Japan, South Korea</span>
<span class="chip"><b>Weekly options</b> required</span>
<span class="chip"><b>&ge; {MIN_BELOW_52W_HIGH_PCT:.0f}%</b> below 52-week high</span>
<span class="chip"><b>IV</b> &ge; floor</span>
<span class="chip"><b>Altman-Z</b> &gt; {MIN_ALTMAN_Z}</span>
</div>
""", unsafe_allow_html=True)

universe = constituents.load_sp500()
has_key = fmp.api_key() is not None

with st.sidebar:
    st.markdown('<div class="side-brand"><i></i>Francine</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-label">Universe</div>', unsafe_allow_html=True)
    if universe.tickers:
        st.caption(f"S&P 500 · {len(universe.tickers)} tickers · list updated "
                   f"{universe.last_updated:%Y-%m-%d %H:%M} UTC ({universe.source})")
    if universe.warning:
        st.warning(universe.warning)

    if not has_key:
        st.error("FMP API key missing.")
        st.markdown(f"Get a free key at [financialmodelingprep.com]({fmp.SIGNUP_URL}), then set "
                    "`FMP_API_KEY` in a `.env` file (see `.env.example`) and restart the app.")
    else:
        u = fmp.usage()
        st.caption(f"FMP requests today: {u['count']} / {u['limit']}")
    st.caption("Free FMP keys cover only ~87 symbols; a full scan accumulates in the cache over several days.")

    st.markdown('<div class="section-label">Parameters</div>', unsafe_allow_html=True)
    pr = st.columns(2)
    price_min = pr[0].number_input("From $", min_value=0.0, value=10.0, step=5.0)
    price_max = pr[1].number_input("To $", min_value=0.0, value=50.0, step=5.0)
    min_iv = st.number_input("Min IV %", min_value=0.0, value=DEFAULT_MIN_IV, step=5.0)

    run = st.button("Run screen", type="primary", use_container_width=True,
                    disabled=not (has_key and universe.tickers))

# ── SCREENING ──────────────────────────────────────────────────────────
if run:
    if price_min <= 0 or price_max <= 0:
        st.error("Enter valid price range.")
    elif price_min >= price_max:
        st.error("'To:' must be greater than 'From:'.")
    else:
        used_before = fmp.usage()["count"]
        loader_ph = st.empty()
        all_qualified, all_failed = run_screen(universe.tickers, universe.names, universe.sectors,
                                               price_min, price_max, min_iv, loader_ph)
        loader_ph.empty()

        st.markdown("---")
        st.markdown("## Results: " + str(len(all_qualified)) + " qualified")

        if all_qualified:
            for q in all_qualified:
                name = html.escape(q.get("company_name", ""))
                ratio = q.get("lt_debt_fcf")
                ratio_txt = f"{ratio:.1f}x" if ratio is not None else "n/m"
                st.markdown(
                    f"<div class='card'><div class='card-head'><div>"
                    f"<div class='card-name'>{name} · {html.escape(q['ticker'])}</div>"
                    f"<div class='card-sub'>{html.escape(q.get('sector', 'N/A'))} / {html.escape(q.get('industry', 'N/A'))}"
                    f" · {html.escape(q.get('hq', ''))}</div></div>"
                    f"<div class='card-price'>${q['price']:.2f}</div></div>"
                    f"<div class='metrics'>"
                    f"<div class='metric'><span>IV</span><b>{q['iv']:.1f}%</b></div>"
                    f"<div class='metric'><span>Altman-Z</span><b>{q['altman_z']:.2f}</b></div>"
                    f"<div class='metric'><span>Below 52-wk high</span><b class='neg'>-{q['pct_below_high']:.1f}%</b></div>"
                    f"<div class='metric'><span>LT debt / FCF</span><b>{ratio_txt}</b></div></div>"
                    f"<div class='driver'>52-week high ${q['year_high']:.2f} · weekly expiry {html.escape(str(q['weekly_exp']))}"
                    f" · LT debt {fmt_money(q.get('lt_debt'))} · FCF {fmt_money(q.get('fcf'))}"
                    f" (FY {html.escape(str(q.get('fin_date') or 'n/a'))})<br>"
                    f"Sources: price/profile/financials FMP (quote {_ts(q.get('quote_at'))}, financials {_ts(q.get('fin_at'))});"
                    f" options/IV Yahoo Finance via yfinance ({_ts(q.get('options_at'))}).</div></div>",
                    unsafe_allow_html=True,
                )

            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(["ticker", "company_name", "price", "year_high", "pct_below_high", "iv",
                        "altman_z", "lt_debt", "fcf", "lt_debt_fcf", "sector", "industry", "hq",
                        "weekly_exp"])
            for q in all_qualified:
                w.writerow([q["ticker"], q["company_name"], q["price"], q["year_high"],
                            round(q["pct_below_high"], 2), q["iv"], round(q["altman_z"], 2),
                            q.get("lt_debt"), q.get("fcf"), q.get("lt_debt_fcf"),
                            q.get("sector"), q.get("industry"), q.get("hq"), q.get("weekly_exp")])
            st.download_button("📥 Download Results as CSV", data=buf.getvalue(),
                               file_name="francine_screener_v3_results.csv", mime="text/csv")
        else:
            st.warning("No qualified companies found.")

        if all_failed:
            with st.expander(f"📊 Screened out ({len(all_failed)} total)"):
                for reason, count in Counter(r.get("fail_group", "Unknown") for r in all_failed).most_common():
                    st.markdown(f"- **{reason}**: {count}")
                st.dataframe(pd.DataFrame(
                    [{"Ticker": r["ticker"], "Company": r.get("company_name", ""), "Reason": r.get("fail_reason", "")}
                     for r in all_failed]), use_container_width=True, hide_index=True)

        u = fmp.usage()
        st.caption(f"FMP requests this run: {u['count'] - used_before} · today: {u['count']} / {u['limit']} · "
                   f"cache hits: {fmp.session_stats()['cache_hits']}")
