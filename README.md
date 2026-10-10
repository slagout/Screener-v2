# 📊 FRANCINE SCREENER V3

A relaxed variant of the Francine Screener. Same engine as V2 but **allows
pharmaceutical, tobacco, and cannabis companies** while still blocking banks,
insurance, and financial services.

**Key difference from V2:** V3 also **requires a weekly options chain** —
companies with only monthly options are rejected.

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

### Step 4: Run the app

Type this and press Enter:

```
streamlit run app.py
```

A browser window should open automatically at **http://localhost:8501**.

If it doesn't open automatically, open your browser and type that address yourself.

### Step 5: Use it

1. Enter a **price range** (From: $25 → To: $75, or any range you want)
2. Click **🚀 RUN SCREEN**
3. Wait ~2-3 minutes while it scans the S&P 500
4. View the results — up to 5 qualified companies with full details

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
| Financial Data | Most recent fiscal year (SEC filings via Yahoo Finance) |

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

## 📁 What's in the folder

```
company-screening-tool-v3/
├── app.py              ← The V3 app itself
├── requirements.txt    ← What the app needs to install
└── README.md           ← This file
```