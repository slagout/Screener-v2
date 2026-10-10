"""Yahoo Finance data via yfinance: quote, profile and annual statements.

Free and keyless, but unofficial, so Yahoo can rate-limit. Results are shaped like the
fields the screen needs (price, yearHigh, marketCap, country, revenue, ...) and cached on
disk in ./cache/ so repeated runs are fast and gentle on Yahoo.
"""
from __future__ import annotations

import json
import math
import os
import threading
import time
from pathlib import Path

import yfinance as yf

_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_TTL = {"quote": 3600, "profile": 7 * 86400, "income": 7 * 86400,
                "balance": 7 * 86400, "cashflow": 7 * 86400}
_lock = threading.Lock()
_stats = {"fetches": 0, "cache_hits": 0}


class YahooError(Exception):
    pass


class YahooRateLimited(YahooError):
    pass


def stats() -> dict:
    with _lock:
        return dict(_stats)


def _cache_dir() -> Path:
    d = Path(os.getenv("YAHOO_CACHE_DIR", str(_ROOT / "cache")))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ttl(kind: str) -> int:
    return int(os.getenv(f"YAHOO_CACHE_TTL_{kind.upper()}", str(_DEFAULT_TTL[kind])))


def _clean(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else f


def _is_rate_limit(exc: Exception) -> bool:
    text = f"{type(exc).__name__} {exc}".lower()
    return "ratelimit" in text or "too many requests" in text or "429" in text


def _cached(kind: str, symbol: str, fetch) -> dict:
    path = _cache_dir() / f"yahoo_{kind}_{symbol.upper()}.json"
    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - entry["ts"] < _ttl(kind):
            with _lock:
                _stats["cache_hits"] += 1
            return {**entry["data"], "_fetched_at": entry["ts"]}
    except (OSError, ValueError, KeyError):
        pass

    last = None
    for attempt in range(2):
        try:
            with _lock:
                _stats["fetches"] += 1
            data = fetch(yf.Ticker(symbol))
            break
        except YahooError:
            raise
        except Exception as exc:
            if _is_rate_limit(exc):
                raise YahooRateLimited("Yahoo Finance rate limit hit") from exc
            last = exc
            time.sleep(1.0 * (attempt + 1))
    else:
        raise YahooError(f"{symbol}: {type(last).__name__}")

    now = time.time()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"ts": now, "data": data}), encoding="utf-8")
    tmp.replace(path)
    return {**data, "_fetched_at": now}


def _row(df, *names):
    for n in names:
        if n in df.index:
            return _clean(df.loc[n].iloc[0])
    return None


def _statement(t, attr: str):
    df = getattr(t, attr)
    if df is None or df.empty:
        raise YahooError(f"no {attr} data")
    return df, str(df.columns[0])[:10]


def get_quote(symbol: str) -> dict:
    def fetch(t):
        fi = t.fast_info
        price, high, cap = _clean(fi["last_price"]), _clean(fi["year_high"]), _clean(fi["market_cap"])
        if not price or not high:
            raise YahooError("no quote data")
        return {"price": price, "yearHigh": high, "marketCap": cap}
    return _cached("quote", symbol, fetch)


def get_profile(symbol: str) -> dict:
    def fetch(t):
        info = t.info
        if not info or not (info.get("sector") or info.get("industry")):
            raise YahooError("no profile data")
        return {"companyName": info.get("longName") or info.get("shortName"),
                "sector": info.get("sector"), "industry": info.get("industry"),
                "country": info.get("country"), "city": info.get("city"),
                "exchange": info.get("exchange")}
    return _cached("profile", symbol, fetch)


def get_income(symbol: str) -> dict:
    def fetch(t):
        df, date = _statement(t, "financials")
        return {"date": date, "revenue": _row(df, "Total Revenue", "Operating Revenue"),
                "ebit": _row(df, "EBIT"), "operatingIncome": _row(df, "Operating Income")}
    return _cached("income", symbol, fetch)


def get_balance(symbol: str) -> dict:
    def fetch(t):
        df, date = _statement(t, "balance_sheet")
        return {"date": date, "totalAssets": _row(df, "Total Assets"),
                "totalLiabilities": _row(df, "Total Liabilities Net Minority Interest"),
                "totalCurrentAssets": _row(df, "Current Assets"),
                "totalCurrentLiabilities": _row(df, "Current Liabilities"),
                "retainedEarnings": _row(df, "Retained Earnings"),
                "longTermDebt": _row(df, "Long Term Debt")}
    return _cached("balance", symbol, fetch)


def get_cashflow(symbol: str) -> dict:
    def fetch(t):
        df, date = _statement(t, "cashflow")
        return {"date": date, "freeCashFlow": _row(df, "Free Cash Flow")}
    return _cached("cashflow", symbol, fetch)
