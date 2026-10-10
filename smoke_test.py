"""End-to-end smoke test for the V3 pipeline (Yahoo Finance, no API key needed).

    python smoke_test.py                 # AAPL and MSFT
    python smoke_test.py KO PFE          # your own symbols
    python smoke_test.py AAPL --no-options

Exits non-zero if anything fails.
"""
import sys
import threading

from data_sources import constituents, options, yahoo

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

    print("== 1. S&P 500 list ==")
    uni = constituents.load_sp500()
    check("universe loaded", len(uni.tickers) >= 450,
          f"{len(uni.tickers)} tickers, source={uni.source}, warning={uni.warning}")

    app = load_app_logic()
    good = {}

    for sym in symbols:
        print(f"\n== 2. Yahoo data for {sym} ==")
        try:
            q = yahoo.get_quote(sym)
            check(f"{sym} quote", all(q.get(k) for k in ("price", "yearHigh", "marketCap")),
                  f"price={q.get('price')} yearHigh={q.get('yearHigh')} marketCap={q.get('marketCap')}")
            p = yahoo.get_profile(sym)
            check(f"{sym} profile", bool(p.get("country") and p.get("industry")),
                  f"{p.get('companyName')} | {p.get('sector')} / {p.get('industry')} | {p.get('country')}")
            check(f"{sym} country allowed", app["country_allowed"](p.get("country")), str(p.get("country")))
            inc, bal, cf = yahoo.get_income(sym), yahoo.get_balance(sym), yahoo.get_cashflow(sym)
            check(f"{sym} income statement", inc.get("revenue") is not None, f"FY {inc.get('date')} revenue={inc.get('revenue')}")
            check(f"{sym} balance sheet", all(bal.get(k) is not None for k in ("totalAssets", "totalLiabilities", "retainedEarnings")),
                  f"longTermDebt={bal.get('longTermDebt')}")
            check(f"{sym} cash flow", cf.get("freeCashFlow") is not None, f"freeCashFlow={cf.get('freeCashFlow')}")
            z = app["altman_z"](inc, bal, q.get("marketCap"))
            check(f"{sym} Altman-Z computed", z is not None, f"{z:.2f}" if z is not None else "missing fields")
            good[sym] = q
        except yahoo.YahooError as exc:
            check(f"{sym} Yahoo fetch", False, str(exc))

    print("\n== 3. Caching ==")
    if good:
        before = yahoo.stats()["fetches"]
        yahoo.get_quote(next(iter(good)))
        check("repeat call served from cache", yahoo.stats()["fetches"] == before)

    if not skip_options:
        print("\n== 4. Options ==")
        for sym, q in good.items():
            o = options.check_options(sym, float(q["price"]))
            check(f"{sym} options fetch", o.status == "ok", f"weekly={o.has_weekly} exp={o.weekly_exp} iv={o.iv} {o.reason}")

    print("\n== 5. Full screen_ticker (strict V3 rules, wide price range) ==")
    for sym in good:
        r = app["screen_ticker"](sym, sym, "", 0, 1e6, app["DEFAULT_MIN_IV"], threading.Event())
        check(f"{sym} reaches a verdict", r["stage"] > 0 or bool(r["fail_reason"]),
              f"qualified={r['qualified']} stage={r['stage']}/4 {r['fail_reason']}")

    if not skip_options and good:
        print("\n== 6. Full screen_ticker (thresholds relaxed so it must run all 4 stages) ==")
        app["MIN_BELOW_52W_HIGH_PCT"] = -1e9
        app["MIN_ALTMAN_Z"] = -1e9
        for sym in good:
            r = app["screen_ticker"](sym, sym, "", 0, 1e6, 0.0, threading.Event())
            ok = r["qualified"] or any(w in r["fail_reason"] for w in ("UNKNOWN", "Monthly-only", "Blocked industry", "Country"))
            check(f"{sym} end-to-end", ok,
                  f"qualified={r['qualified']} stage={r['stage']}/4 {r['fail_reason']}"
                  + (f" | IV {r['iv']}% Z {r['altman_z']:.2f}" if r["qualified"] else ""))

    print("\nRESULT:", "ALL CHECKS PASSED" if not failures else f"{len(failures)} FAILED: " + "; ".join(failures))
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
