# 📊 FRANCINE SCREENER V3

A relaxed variant of the Francine Screener. Same engine as V2 but **allows
pharmaceutical, tobacco, and cannabis companies** while still blocking banks,
insurance, and financial services.

**Key difference from V2:** V3 also **requires a weekly options chain** —
companies with only monthly options are rejected.

> **Data source:** prices, company profile and financial statements come from Yahoo Finance
> (via `yfinance`) — free, no API key. It is an unofficial feed, so Yahoo can occasionally
> rate-limit very large scans; results are cached in `./cache/` so re-runs are fast and gentle.
> A full S&P 500 scan takes a few minutes.

---

## 🚀 HOW TO RUN — Step by Step (takes ~5 minutes)

### Step 1: Make sure Python is installed

1. Open a **Command Prompt**: press `Windows key`, type `cmd`, press Enter.
2. Type this and press Enter:
   ```
   python --version
   ```
3. If you see something like `Python 3.x.x` → you're good, go to Step 2.
4. If you get an error or "not recognized":
   - Go to https://www.python.org/downloads/
   - Click the big **Download Python** button
   - Run the installer
   - **IMPORTANT:** Tick the box **"Add Python to PATH"** at the bottom of the first screen
   - Click Install Now, then close

### Step 2: Open the folder

1. Unzip the `company-screening-tool-v3` folder wherever you like
2. In the Command Prompt, navigate into it:
   ```
   cd path\to\company-screening-tool-v3
   ```
   (Or: type `cd `, drag the folder into the Command Prompt window, press Enter)

### Step 3: Install the app (one time only)

Copy and paste these three lines **one at a time**, pressing Enter after each:

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

(You'll see `(.venv)` appear at the start of the line — that's normal and good.)

### Step 3b: (Optional) check everything works

No API key is needed. This quick test pulls live data for AAPL and MSFT and runs the whole pipeline:

```
python smoke_test.py            # or: python smoke_test.py KO PFE --no-options
```

Optional cache lifetimes in seconds (environment variables): `YAHOO_CACHE_TTL_QUOTE` (3600),
`YAHOO_CACHE_TTL_PROFILE`, `YAHOO_CACHE_TTL_INCOME`, `YAHOO_CACHE_TTL_BALANCE`,
`YAHOO_CACHE_TTL_CASHFLOW` (7 days each).

### Step 4: Run the app

Type this and press Enter:

```
streamlit run app.py
```

A browser window should open automatically at **http://localhost:8501**.

If it doesn't open automatically, open your browser and type that address yourself.

### Step 5: Use it

1. Enter a **price range** (From: $25 → To: $75, or any range you want) and a minimum IV
2. Click **Run screen**
3. Wait while it works through the S&P 500
4. View the results — every company that passes all filters, with full details

### When you're done

Press `Ctrl + C` in the Command Prompt window to stop the app. Close the window.

---

## 🔎 What it checks (all requirements mandatory)

| Filter | Requirement |
|--------|------------|
| Universe | S&P 500 only |
| Industry Exclusions | **Banking, Insurance, Lending, Financial Services** (pharma, tobacco, cannabis ALLOWED) |
| Geographic | US, Canada, Europe, UK, Australia/NZ, Japan, South Korea (avoids China/Russia/Latin America) |
| Options Chain | **WEEKLY OPTIONS REQUIRED** — monthly-only options chains are rejected |
| Price Range | User-defined (From $X – To $Y) |
| 52-Week High | ≥ 25% below high |
| Implied Volatility | ≥ 30% |
| Altman-Z Score | > 3.0 |
| Financial Data | Most recent fiscal year, annual statements (Yahoo Finance) |
| Data sources | Prices, profile, statements, weekly options and IV: Yahoo Finance via yfinance. S&P 500 list: open dataset, cached daily in `sp500.csv`. |
| Failures | A fetch failure is UNKNOWN and the ticker is skipped, never passed |

A company appears in the results **only if it passes every single check**.

---

## 📋 What you see in the results

- **Company details:** name, headquarters, sector/industry, weekly options status, current price, 52-week high, % below high, implied volatility
- **Financial strength table:** Altman-Z score, Long-Term Debt, Free Cash Flow, LT Debt / FCF ratio, weekly options indicator
- **Data transparency:** every price and figure shows its source and timestamp
- Price verification statement for every qualifying company

---

## 🆚 V2 vs V3 Comparison

| | V2 (strict) | V3 (relaxed) |
|--|-------------|--------------|
| Pharma | ❌ Blocked | ✅ Allowed |
| Tobacco | ❌ Blocked | ✅ Allowed |
| Cannabis / Vaping | ❌ Blocked | ✅ Allowed |
| Banks / Insurance | ❌ Blocked | ❌ Blocked |
| Financial Services | ❌ Blocked | ❌ Blocked |
| Weekly Options | Optional check | **Required** — monthly-only rejected |

Both screeners can live side-by-side on the same machine. Just run them on
different ports: `streamlit run app.py --server.port 8501` for V2 and
`streamlit run app.py --server.port 8502` for V3.

## 🛠️ Troubleshooting

| Problem | Fix |
|---------|-----|
| `'python' is not recognized` | Python isn't installed or not on PATH — redo Step 1, tick "Add Python to PATH" |
| `pip` errors | Re-run Step 3 lines one at a time. Make sure the `(.venv)` marker is showing |
| Browser doesn't open | Type `http://localhost:8501` manually in any browser |
| App says "No companies found" | No S&P 500 company currently passes ALL V3 filters in your range. Try a wider range |
| Port already in use | Run `streamlit run app.py --server.port 8502` instead |
| Many tickers show "UNKNOWN" or "Skipped (Yahoo unavailable)" | Yahoo rate-limited the scan. Wait a few minutes and run again — cached data is reused |

## 📁 What's in the folder

```
company-screening-tool-v3/
├── app.py              ← The V3 app itself
├── data_sources/       ← yahoo.py (quote/profile/statements), options.py (weekly/IV), constituents.py (S&P 500 list)
├── smoke_test.py      ← Optional end-to-end check
├── requirements.txt    ← What the app needs to install
└── README.md           ← This file
```