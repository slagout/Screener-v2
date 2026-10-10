"""Financial Modeling Prep (FMP) client: every FMP call in the app goes through here.

Endpoints (verified against FMP's docs, base https://financialmodelingprep.com/stable):
  quote, profile, income-statement, balance-sheet-statement, cash-flow-statement.

FMP free tier: 250 requests/day, annual statements only (we only need the most
recent fiscal year), and only ~87 symbols are queryable. Responses are cached on
disk (./cache/, survives restarts) and the daily request count is persisted so
the budget is enforced across restarts.
"""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_ROOT / ".env")

BASE_URL = "https://financialmodelingprep.com/stable"
SIGNUP_URL = "https://site.financialmodelingprep.com/register"
DAILY_LIMIT = int(os.getenv("FMP_DAILY_LIMIT", "250"))

# Cache TTLs in seconds, overridable via env.
_DEFAULT_TTL = {"quote": 3600, "profile": 7 * 86400,
                "income": 7 * 86400, "balance": 7 * 86400, "cashflow": 7 * 86400}
# Plan restrictions don't change, so remember them long to avoid re-spending calls.
RESTRICTED_TTL = int(os.getenv("FMP_CACHE_TTL_RESTRICTED", str(7 * 86400)))


class FMPError(Exception):
    pass


class FMPAuthError(FMPError):
    pass


class FMPPlanRestricted(FMPError):
    pass


class FMPBudgetExhausted(FMPError):
    pass


class FMPRateLimited(FMPError):
    pass


class FMPDataError(FMPError):
    pass


_lock = threading.Lock()
_session = {"requests": 0, "cache_hits": 0}


def api_key() -> str | None:
    key = os.getenv("FMP_API_KEY", "").strip()
    if not key:
        # Streamlit Cloud keeps secrets in st.secrets (not GitHub secrets).
        try:
            import streamlit as st
            key = str(st.secrets.get("FMP_API_KEY", "")).strip()
        except Exception:
            key = ""
    return key or None


def _cache_dir() -> Path:
    d = Path(os.getenv("FMP_CACHE_DIR", str(_ROOT / "cache")))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ttl(kind: str) -> int:
    return int(os.getenv(f"FMP_CACHE_TTL_{kind.upper()}", str(_DEFAULT_TTL[kind])))


def _write_json(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.replace(path)


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _read_usage() -> dict:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    data = _read_json(_cache_dir() / "_usage.json") or {}
    if data.get("date") != today:
        data = {"date": today, "count": 0}
    return data


def usage() -> dict:
    """Requests spent today (UTC) across all runs, plus the daily limit."""
    with _lock:
        u = _read_usage()
    return {"date": u["date"], "count": u["count"], "limit": DAILY_LIMIT}


def session_stats() -> dict:
    with _lock:
        return dict(_session)


def _spend() -> None:
    with _lock:
        u = _read_usage()
        if u["count"] >= DAILY_LIMIT:
            raise FMPBudgetExhausted(f"FMP daily budget of {DAILY_LIMIT} requests reached")
        u["count"] += 1
        _write_json(_cache_dir() / "_usage.json", u)
        _session["requests"] += 1


def _request(path: str, params: dict):
    key = api_key()
    if not key:
        raise FMPAuthError("FMP_API_KEY is not set")
    _spend()
    try:
        resp = requests.get(f"{BASE_URL}/{path}", params=params,
                            headers={"apikey": key}, timeout=20)
    except requests.RequestException as exc:
        raise FMPDataError(f"network error: {type(exc).__name__}") from exc

    if resp.status_code == 401:
        raise FMPAuthError("FMP rejected the API key")
    if resp.status_code in (402, 403):
        raise FMPPlanRestricted(f"{path} not available on this FMP plan")
    if resp.status_code == 429:
        raise FMPRateLimited("FMP rate limit hit")
    if resp.status_code >= 400:
        raise FMPDataError(f"HTTP {resp.status_code}")

    try:
        body = resp.json()
    except ValueError as exc:
        raise FMPDataError("invalid JSON from FMP") from exc

    if isinstance(body, dict) and "Error Message" in body:
        msg = str(body["Error Message"]).lower()
        if "limit" in msg:
            raise FMPRateLimited(body["Error Message"])
        if "invalid api key" in msg:
            raise FMPAuthError(body["Error Message"])
        if any(w in msg for w in ("restricted", "subscription", "premium", "upgrade", "not available")):
            raise FMPPlanRestricted(body["Error Message"])
        raise FMPDataError(str(body["Error Message"])[:120])

    if isinstance(body, list):
        return body[0] if body else {}
    return body if isinstance(body, dict) else {}


def _cached(kind: str, symbol: str, path: str, params: dict) -> dict:
    symbol = symbol.upper()
    f = _cache_dir() / f"{kind}_{symbol}.json"
    entry = _read_json(f)
    if entry:
        age = time.time() - entry.get("ts", 0)
        if entry.get("status") == "restricted" and age < RESTRICTED_TTL:
            with _lock:
                _session["cache_hits"] += 1
            raise FMPPlanRestricted(f"{symbol}: not covered by FMP plan (cached)")
        if entry.get("status") == "ok" and age < _ttl(kind):
            with _lock:
                _session["cache_hits"] += 1
            return {**entry["data"], "_fetched_at": entry["ts"]}
    try:
        data = _request(path, {**params, "symbol": symbol})
    except FMPPlanRestricted:
        _write_json(f, {"ts": time.time(), "status": "restricted", "data": {}})
        raise
    now = time.time()
    _write_json(f, {"ts": now, "status": "ok", "data": data})
    return {**data, "_fetched_at": now}


def get_quote(symbol: str) -> dict:
    """price, yearHigh, marketCap, ..."""
    return _cached("quote", symbol, "quote", {})


def get_profile(symbol: str) -> dict:
    """sector, industry, country, city, exchange, ..."""
    return _cached("profile", symbol, "profile", {})


# Annual statements only: the free tier has no quarterly data and the screen
# uses the most recent fiscal year.
_STATEMENT_PARAMS = {"period": "annual", "limit": 1}


def get_income(symbol: str) -> dict:
    return _cached("income", symbol, "income-statement", _STATEMENT_PARAMS)


def get_balance(symbol: str) -> dict:
    return _cached("balance", symbol, "balance-sheet-statement", _STATEMENT_PARAMS)


def get_cashflow(symbol: str) -> dict:
    return _cached("cashflow", symbol, "cash-flow-statement", _STATEMENT_PARAMS)
