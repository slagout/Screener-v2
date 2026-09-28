# Francine Screener v2 - Complete Mac Package

## Package Contents

This is a complete package for distributing the Francine Screener v2 as a Mac application. The package includes all necessary files to create a proper Mac DMG installer.

## Files Included

1. **APP_DESCRIPTION.md** - Description of the application
2. **INSTALLATION_GUIDE.md** - Complete installation instructions for creating the DMG
3. **README.md** - General package information
4. **README.txt** - Simple text-based readme
5. **LICENSE.txt** - MIT License
6. **install.sh** - Installation script (for Unix-like systems)

## Creating the Mac DMG

Since we're in a Windows environment, here's what you need to do:

### Method 1: Manual Creation (on Mac)

1. **Prepare the Application Bundle**:
   - Create a folder named `FrancineScreener.app`
   - Inside, create the following structure:
     ```
     Contents/
     ├── Info.plist
     ├── MacOS/
     │   ├── run_app (executable script)
     │   ├── app.py
     │   └── requirements.txt
     └── Resources/
     ```

2. **Create Required Files**:
   - **Info.plist**: Contains application metadata
   - **run_app**: Launcher script with executable permissions
   - **app.py**: Main application code (from your repository)
   - **requirements.txt**: Python dependencies

3. **Build the DMG**:
   ```bash
   hdiutil create -srcfolder FrancineScreener.app -volname "FrancineScreener" -format UDZO -imagekey zlib-level=9 francine-screener-v2.dmg
   ```

### Method 2: Automated Approach

Use a Python tool like `py2app` on a Mac:

1. Install py2app:
   ```bash
   pip install py2app
   ```

2. Create setup.py:
   ```python
   from setuptools import setup

   APP = ['app.py']
   DATA_FILES = []
   OPTIONS = {
       'argv_emulation': True,
       'packages': ['streamlit', 'yfinance', 'pandas', 'numpy', 'requests', 'altair'],
       'plist': {
           'CFBundleName': 'FrancineScreener',
           'CFBundleDisplayName': 'Francine Screener v2',
           'CFBundleIdentifier': 'com.francine.screener.v2',
           'CFBundleVersion': '2.0.0',
           'CFBundleShortVersionString': '2.0.0',
       }
   }

   setup(
       app=APP,
       data_files=DATA_FILES,
       options={'py2app': OPTIONS},
       setup_requires=['py2app'],
   )
   ```

3. Build the app:
   ```bash
   python setup.py py2app
   ```

## Requirements

- macOS 10.15 or higher
- Python 3.8 or higher
- Internet connection for data fetching

## Features

- Screens S&P 500 stocks using institutional methodology
- Industry and geographic filtering
- Price range selection
- Options liquidity checking
- Implied volatility filtering
- Operating margin analysis
- Revenue CAGR calculation
- Web-based interface via Streamlit

## Important Notes

1. The application requires internet connectivity to fetch market data
2. The first run will install dependencies into a virtual environment
3. The application opens automatically in your default browser
4. Users should have Python 3.8+ installed on their system

## Distribution

Once you've created the DMG file, you can:
- Host it on your website
- Share via cloud storage
- Include it in a software distribution package
- Provide it as a downloadable installer

This package ensures that Mac users can easily run the Francine Screener without needing to manually install Python or dependencies.