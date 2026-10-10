"""S&P 500 constituents from a maintained open dataset, with a validated local CSV cache.

FMP's own constituents endpoint (/stable/sp500-constituent) is Premium-only, so the
free path uses the open dataset below. The list is refreshed at most once a day and
cached to sp500.csv, which is also the fallback when the remote fetch or validation fails.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

SOURCE_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
CACHE_FILE = Path(__file__).resolve().parents[1] / "sp500.csv"
REFRESH_AFTER = timedelta(days=1)
MIN_COUNT, MAX_COUNT = 450, 550
_TICKER_RE = re.compile(r"^[A-Z.\-]+$")


@dataclass
class Universe:
    tickers: list[str] = field(default_factory=list)
    names: dict[str, str] = field(default_factory=dict)
    sectors: dict[str, str] = field(default_factory=dict)  # "Sector / Sub-Industry"
    last_updated: datetime | None = None
    source: str = "none"  # "remote" | "cache" | "none"
    warning: str | None = None


def _validate(df: pd.DataFrame) -> str | None:
    if not {"symbol", "name", "sector", "sub_industry"} <= set(df.columns):
        return "missing expected columns"
    if not MIN_COUNT <= len(df) <= MAX_COUNT:
        return f"unexpected row count ({len(df)})"
    bad = [s for s in df["symbol"] if not _TICKER_RE.match(str(s))]
    if bad:
        return f"invalid tickers, e.g. {bad[:3]}"
    return None


def _fetch_remote() -> pd.DataFrame:
    resp = requests.get(SOURCE_URL, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    raw = pd.read_csv(io.StringIO(resp.text))
    return pd.DataFrame({
        "symbol": raw["Symbol"].astype(str).str.strip(),
        "name": raw["Security"].astype(str).str.strip(),
        "sector": raw["GICS Sector"].astype(str).str.strip(),
        "sub_industry": raw["GICS Sub-Industry"].astype(str).str.strip(),
    })


def _read_cache() -> pd.DataFrame | None:
    try:
        df = pd.read_csv(CACHE_FILE)
    except (OSError, ValueError):
        return None
    return df if _validate(df) is None and "updated" in df.columns else None


def _to_universe(df: pd.DataFrame, source: str, warning: str | None) -> Universe:
    # yfinance/FMP use "BRK-B", the dataset uses "BRK.B".
    syms = df["symbol"].str.replace(".", "-", regex=False)
    return Universe(
        tickers=syms.tolist(),
        names=dict(zip(syms, df["name"])),
        sectors=dict(zip(syms, df["sector"] + " / " + df["sub_industry"])),
        last_updated=pd.to_datetime(df["updated"].iloc[0], utc=True).to_pydatetime(),
        source=source,
        warning=warning,
    )


def load_sp500() -> Universe:
    cached = _read_cache()
    if cached is not None:
        age = datetime.now(timezone.utc) - pd.to_datetime(cached["updated"].iloc[0], utc=True).to_pydatetime()
        if age < REFRESH_AFTER:
            return _to_universe(cached, "cache", None)

    warning = None
    try:
        fresh = _fetch_remote()
        problem = _validate(fresh)
        if problem is None:
            fresh["updated"] = datetime.now(timezone.utc).isoformat()
            fresh.to_csv(CACHE_FILE, index=False)
            return _to_universe(fresh, "remote", None)
        warning = f"Remote S&P 500 list failed validation ({problem})."
    except Exception as exc:
        warning = f"Could not fetch the S&P 500 list ({type(exc).__name__})."

    if cached is not None:
        return _to_universe(cached, "cache", f"{warning} Using the cached copy.")
    return Universe(warning=f"{warning} No cached copy available.")
