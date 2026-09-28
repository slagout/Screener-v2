# Francine Screener v2 - Python Application Bundle

This is a self-contained Python application for Mac OS X that runs the Francine Screener v2.

## Features
- Screens S&P 500 stocks using Francine's institutional methodology
- Filters by industry, geography, price range, options liquidity, implied volatility, and more
- Displays qualified companies with detailed metrics
- Provides top picks for income strategies

## Requirements
- macOS 10.15 or higher
- Python 3.8 or higher (included in the package)

## Installation
1. Download the .dmg file
2. Mount the disk image
3. Drag the FrancineScreener.app to your Applications folder
4. Launch from Applications folder

## Usage
1. Double-click the FrancineScreener.app icon
2. Set your screening parameters
3. Click "RUN FRANCINE SCREEN v2"
4. View results in your browser

## Technical Details
The application uses:
- Streamlit for the web interface
- yfinance for market data
- Pandas for data processing
- NumPy for numerical computations