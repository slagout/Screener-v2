# 📊 FRANCINE SCREENER V3

A relaxed variant of the Francine Screener. Same engine as V2 but **allows
pharmaceutical, tobacco, and cannabis companies** while still blocking banks,
insurance, and financial services.

**Key difference from V2:** V3 also **requires a weekly options chain** —
companies with only monthly options are rejected.

> **Important — FMP free keys are very limited.** Prices, fundamentals and company data now
> come from [Financial Modeling Prep](https://site.financialmodelingprep.com/register). A free key
> allows **250 requests/day** *and* can only query roughly **87 symbols** (AAPL, TSLA, AMZN and
> about 84 others); the rest are rejected as "not covered by your plan". A full 500-ticker scan
> on a free key will therefore take **multiple days of cached accumulation** and will never cover
> the whole index. Upgrade to a paid plan (Starter and up) for full coverage. Every ticker costs
> up to 5 requests, so the app tests the cheapest filters first and caches every response in
> `./cache/` (it survives restarts).

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

### Step 3b: Add your FMP API key (one time only)

1. Create a free account at https://site.financialmodelingprep.com/register and copy your API key.
2. Copy `.env.example` to `.env` and replace `your_key_here` with your key:
   ```
   FMP_API_KEY=your_key_here
   ```
3. `.env` is git-ignored — never commit it. (On Streamlit Community Cloud, add `FMP_API_KEY` under
   the app's **Secrets** instead; note its disk cache is wiped on restart.)

Without a key the app shows a message in the sidebar and the Run button stays disabled.
Optional tuning in `.env`: `FMP_DAILY_LIMIT` (default 250) and cache lifetimes in seconds
`FMP_CACHE_TTL_QUOTE` (3600), `FMP_CACHE_TTL_PROFILE`, `FMP_CACHE_TTL_INCOME`,
`FMP_CACHE_TTL_BALANCE`, `FMP_CACHE_TTL_CASHFLOW` (7 days each).

Optional check that your key and the whole pipeline work (uses about 10 of your 250 daily requests):

```
python smoke_test.py            # or: python smoke_test.py KO PFE --no-options
```

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
3. Wait while it works through the S&P 500 (a free key stops at its 250-request daily budget)
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
| Financial Data | Most recent fiscal year, annual statements (Financial Modeling Prep) |
| Data sources | Prices, profile, statements: FMP. Weekly options and IV: Yahoo Finance via yfinance (FMP has no options data). S&P 500 list: open dataset, cached daily in `sp500.csv`. |
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
| Sidebar says "FMP API key missing" | Create `.env` from `.env.example` (Step 3b) and restart |
| Many tickers "Not covered by FMP plan" | Free keys only cover ~87 symbols; upgrade your FMP plan |
| "Stopped: FMP daily budget" | The 250-request/day limit was hit; run again tomorrow — cached results are reused |

## 📁 What's in the folder

```
company-screening-tool-v3/
├── app.py              ← The V3 app itself
├── data_sources/       ← fmp.py (FMP + cache), options.py (weekly/IV), constituents.py (S&P 500 list)
├── .env.example        ← Copy to .env and add your FMP key
├── requirements.txt    ← What the app needs to install
└── README.md           ← This file
```