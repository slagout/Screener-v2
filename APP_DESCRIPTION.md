# Francine Screener v2 - Mac Application Bundle

## Overview

This is a complete Mac application package for the Francine Screener v2. The application allows users to screen S&P 500 stocks using institutional-grade criteria.

## Package Structure

```
FrancineScreener.app/
├── Contents/
│   ├── Info.plist
│   ├── MacOS/
│   │   ├── run_app
│   │   ├── app.py
│   │   └── requirements.txt
│   └── Resources/
└── README.txt
```

## Files Included

1. **app.py** - The main application code
2. **requirements.txt** - Python dependencies
3. **run_app** - Launcher script for the application
4. **Info.plist** - Application metadata for macOS
5. **README.txt** - Basic usage instructions
6. **LICENSE.txt** - MIT License
7. **INSTALLATION_GUIDE.md** - Complete installation instructions

## How to Use This Package

1. Copy all files to a folder on your Mac
2. Make the run_app script executable:
   ```bash
   chmod +x run_app
   ```
3. Run the application:
   ```bash
   ./run_app
   ```

## Prerequisites

- macOS 10.15 or higher
- Python 3.8 or higher (included in the package)
- Internet connection for data fetching

## Features

- Screens S&P 500 stocks using Francine's institutional methodology
- Filters by industry, geography, price range, options liquidity, implied volatility
- Displays qualified companies with detailed metrics
- Provides top picks for income strategies
- Web-based interface using Streamlit