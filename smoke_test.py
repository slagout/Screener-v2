"""End-to-end smoke test for the V3 pipeline. Needs a real FMP key (FMP_API_KEY in .env).

    python smoke_test.py                 # AAPL and MSFT, ~10 FMP requests
    python smoke_test.py KO PFE          # your own symbols (free keys: stick to covered ones)
    python smoke_test.py AAPL --no-options

Each symbol costs up to 5 FMP requests, so the default run uses about 10 of the 250/day.
Exits non-zero if anything fails.
"""
import sys
import threading
import time

from data_sources import constituents, fmp, options

failures = []


def check(label, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f" - {detail}" if detail else ""))
    if not ok:
        failures.append(label)
    return ok


def load_app_logic():
    """Run the pure screening code from app.py without starting the Streamlit UI."""
    src = open("app.py", encoding="utf-8").read()
    marker = "def render_progress("
    if marker not in src:
        raise SystemExit("smoke_test.py: app.py layout changed, update load_app_logic()")
    head = src.split(marker)[0].replace("st.set_page_config(", "(lambda **k: None)(")
    ns = {"__name__": "app_logic"}
    exec(compile(head, "app.py", "exec"), ns)
    return ns


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    symbols = [a.upper() for a in args] or ["AAPL", "MSFT"]
    skip_options = "--no-options" in sys.argv

    print("== 1. API key ==")
    if not check("FMP_API_KEY is set", fmp.api_key() is not None):
        print("Copy .env.example to .env and add your key.")
        raise SystemExit(1)
    start = fmp.usage()["count"]

    print("\n== 2. S&P 500 list ==")
    uni = constituents.load_sp500()
    check("universe loaded", len(uni.tickers) >= 450,
          f"{len(uni.tickers)} tickers, source={uni.source}, warning={uni.warning}")

    app = load_app_logic()
    now_ok = {}

    for sym in symbols:
        print(f"\n== 3. FMP data for {sym} ==")
        try:
            q = fmp.get_quote(sym)
            check(f"{sym} quote", all(q.get(k) for k in ("price", "yearHigh", "marketCap")),
                  f"price={q.get('price')} yearHigh={q.get('yearHigh')} marketCap={q.get('marketCap')}")
            p = fmp.get_profile(sym)
            check(f"{sym} profile", bool(p.get("country") and p.get("industry")),
                  f"{p.get('companyName')} | {p.get('sector')} / {p.get('industry')} | {p.get('country')}")
            inc, bal, cf = fmp.get_income(sym), fmp.get_balance(sym), fmp.get_cashflow(sym)
            check(f"{sym} income statement", "revenue" in inc and ("ebit" in inc or "operatingIncome" in inc),
                  f"FY {inc.get('date')} revenue={inc.get('revenue')}")
            check(f"{sym} balance sheet", all(k in bal for k in ("totalAssets", "totalLiabilities", "retainedEarnings")),
                  f"longTermDebt={bal.get('longTermDebt')}")
            check(f"{sym} cash flow", "freeCashFlow" in cf, f"freeCashFlow={cf.get('freeCashFlow')}")
            z = app["altman_z"](inc, bal, q.get("marketCap"))
            check(f"{sym} Altman-Z computed", z is not None, f"{z:.2f}" if z is not None else "missing fields")
            now_ok[sym] = q
        except fmp.FMPPlanRestricted:
            check(f"{sym} covered by your FMP plan", False, "free keys only cover ~87 symbols; try another")
        except fmp.FMPError as exc:
            check(f"{sym} FMP fetch", False, str(exc))

    print("\n== 4. Caching ==")
    if now_ok:
        before = fmp.usage()["count"]
        fmp.get_quote(next(iter(now_ok)))
        check("repeat call served from cache (no request spent)", fmp.usage()["count"] == before)

    if not skip_options:
        print("\n== 5. Options (yfinance) ==")
        for sym, q in now_ok.items():
            o = options.check_options(sym, float(q["price"]))
            check(f"{sym} options fetch", o.status == "ok", f"weekly={o.has_weekly} exp={o.weekly_exp} iv={o.iv} {o.reason}")

    print("\n== 6. Full screen_ticker (strict V3 rules, wide price range) ==")
    for sym in now_ok:
        r = app["screen_ticker"](sym, sym, "", 0, 1e6, app["DEFAULT_MIN_IV"], threading.Event())
        check(f"{sym} reaches a verdict", r["stage"] > 0 or bool(r["fail_reason"]),
              f"qualified={r['qualified']} stage={r['stage']}/4 {r['fail_reason']}")

    if not skip_options and now_ok:
        print("\n== 7. Full screen_ticker (thresholds relaxed so it must run all 4 stages) ==")
        app["MIN_BELOW_52W_HIGH_PCT"] = -1e9
        app["MIN_ALTMAN_Z"] = -1e9
        for sym in now_ok:
            r = app["screen_ticker"](sym, sym, "", 0, 1e6, 0.0, threading.Event())
            reasons_ok = r["qualified"] or "UNKNOWN" in r["fail_reason"] or "Monthly-only" in r["fail_reason"] \
                or "Blocked industry" in r["fail_reason"] or "Country" in r["fail_reason"]
            check(f"{sym} end-to-end", reasons_ok,
                  f"qualified={r['qualified']} stage={r['stage']}/4 {r['fail_reason']}"
                  + (f" | IV {r['iv']}% Z {r['altman_z']:.2f}" if r["qualified"] else ""))

    u = fmp.usage()
    print(f"\nFMP requests this test: {u['count'] - start} (today {u['count']}/{u['limit']})")
    print("RESULT:", "ALL CHECKS PASSED" if not failures else f"{len(failures)} FAILED: " + "; ".join(failures))
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
