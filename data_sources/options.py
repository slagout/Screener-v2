"""Options data (weekly detection + implied volatility) via yfinance.

FMP has no options endpoints, so this is the only module that touches yfinance.
Any fetch failure returns status "unknown" so the caller skips the ticker.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

import yfinance as yf

WEEKLY_WINDOW_DAYS = 9
# When the near window's expiry is the monthly (third Friday), that slot is shared with
# the weekly, so allow the next non-monthly expiry one week further out.
WEEKLY_GRACE_DAYS = 7
MIN_STRIKES = 5


@dataclass
class OptionsResult:
    status: str  # "ok" | "unknown"
    has_weekly: bool = False
    weekly_exp: str | None = None
    iv: float | None = None
    reason: str = ""
    fetched_at: float = 0.0


def _is_monthly(d: date) -> bool:
    # Standard monthly expiry is the third Friday.
    return d.weekday() == 4 and 15 <= d.day <= 21


def _tradeable(chain) -> bool:
    strikes = set(chain.calls["strike"]) | set(chain.puts["strike"])
    if len(strikes) < MIN_STRIKES:
        return False
    activity = 0.0
    for frame in (chain.calls, chain.puts):
        for col in ("openInterest", "volume"):
            if col in frame:
                activity += float(frame[col].fillna(0).sum())
    return activity > 0


def _near_iv(frame, price: float, now: datetime, tte: float) -> float | None:
    """Back out IV from the at-the-money option price (price ≈ 0.4·S·σ·√T)."""
    if frame.empty or tte <= 0.001:
        return None
    row = frame.loc[(frame["strike"] - price).abs().idxmin()]
    mid = (float(row.get("bid", 0) or 0) + float(row.get("ask", 0) or 0)) / 2
    opt_price = mid if mid > 0.01 else float(row.get("lastPrice", 0) or 0)
    if opt_price <= 0.01:
        return None
    approx = opt_price / (price * 0.4 * (tte ** 0.5))
    return approx * 100 if 0.01 < approx < 5.0 else None


def _implied_vol(stock, exps: list[str], price: float) -> float | None:
    now = datetime.now()
    target = now + timedelta(days=30)
    try:
        best = min(exps, key=lambda e: abs((datetime.strptime(e[:10], "%Y-%m-%d") - target).days))
        chain = stock.option_chain(best)
        tte = (datetime.strptime(best[:10], "%Y-%m-%d") - now).days / 365.0
        for frame in (chain.calls, chain.puts):
            iv = _near_iv(frame, price, now, tte)
            if iv is not None:
                return round(iv, 1)
    except Exception:
        pass
    for exp in exps[:5]:
        try:
            calls = stock.option_chain(exp).calls
            if calls.empty:
                continue
            row = calls.loc[(calls["strike"] - price).abs().idxmin()]
            iv = row.get("impliedVolatility")
            if iv and float(iv) > 0.001:
                return round(float(iv) * 100, 1)
        except Exception:
            continue
    return None


def check_options(ticker: str, price: float) -> OptionsResult:
    import time

    try:
        stock = yf.Ticker(ticker)
        exps = list(stock.options or [])
    except Exception as exc:
        return OptionsResult("unknown", reason=f"UNKNOWN: options fetch failed ({type(exc).__name__})")
    if not exps:
        return OptionsResult("unknown", reason="UNKNOWN: no option expirations returned")

    today = date.today()
    parsed = []
    for e in exps:
        try:
            d = datetime.strptime(e[:10], "%Y-%m-%d").date()
        except ValueError:
            continue
        parsed.append((e, (d - today).days, _is_monthly(d)))
    candidates = [e for e, days, monthly in parsed if 0 <= days <= WEEKLY_WINDOW_DAYS and not monthly]
    if not candidates and any(0 <= days <= WEEKLY_WINDOW_DAYS and monthly for _, days, monthly in parsed):
        candidates = [e for e, days, monthly in parsed
                      if 0 <= days <= WEEKLY_WINDOW_DAYS + WEEKLY_GRACE_DAYS and not monthly]
    if not candidates:
        return OptionsResult(
            "ok", reason=f"Monthly-only options (no weekly expiry within {WEEKLY_WINDOW_DAYS} days)")

    weekly_exp = None
    for e in candidates:
        try:
            if _tradeable(stock.option_chain(e)):
                weekly_exp = e
                break
        except Exception as exc:
            return OptionsResult("unknown", reason=f"UNKNOWN: option chain fetch failed ({type(exc).__name__})")
    if weekly_exp is None:
        return OptionsResult("ok", reason="Weekly chain not tradeable (too few strikes or no activity)")

    return OptionsResult("ok", has_weekly=True, weekly_exp=weekly_exp,
                         iv=_implied_vol(stock, exps, price), fetched_at=time.time())
