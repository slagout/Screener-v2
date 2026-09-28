# Francine Screener v2 - Mac Distribution Package

## Package Contents

This package contains everything needed to distribute the Francine Screener v2 as a Mac application:

1. `FrancineScreener.app` - The main application bundle
2. `install.sh` - Installation script for Mac users
3. `README.md` - Detailed installation and usage instructions
4. `LICENSE.txt` - MIT License information
5. `requirements.txt` - Python dependencies
6. `app.py` - Main application code

## How to Create the DMG File

Since we're in a Windows environment, you'll need to use a Mac to create the final DMG file. Here's the process:

### Step 1: Prepare the Application Structure

Create the following directory structure on Mac:
```
FrancineScreener.app/
├── Contents/
│   ├── Info.plist
│   ├── MacOS/
│   │   ├── run_app (executable script)
│   │   ├── app.py
│   │   └── requirements.txt
│   └── Resources/
│       └── app.icns (application icon)
```

### Step 2: Create Required Files

1. **Info.plist** (inside Contents/)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>English</string>
    <key>CFBundleExecutable</key>
    <string>run_app</string>
    <key>CFBundleIconFile</key>
    <string>app.icns</string>
    <key>CFBundleIdentifier</key>
    <string>com.francine.screener.v2</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>FrancineScreener</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>2.0.0</string>
    <key>CFBundleSignature</key>
    <string>????</string>
    <key>CFBundleVersion</key>
    <string>2.0.0</string>
    <key>NSPrincipalClass</key>
    <string>NSApplication</string>
</dict>
</plist>
```

2. **run_app** (inside Contents/MacOS/, make executable with chmod +x)
```bash
#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the directory containing the app
cd "$SCRIPT_DIR"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies if needed
if ! pip list | grep -q streamlit; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

# Run the application
echo "Starting Francine Screener v2..."
streamlit run app.py
```

3. **requirements.txt** (inside Contents/MacOS/)
```
streamlit==1.40.2
yfinance==0.2.54
pandas==2.2.3
numpy==2.0.2
requests==2.32.3
altair==5.5.0
```

### Step 3: Create the DMG File

On Mac, use the following command:
```bash
hdiutil create -srcfolder FrancineScreener.app -volname "FrancineScreener" -format UDZO -imagekey zlib-level=9 francine-screener-v2.dmg
```

## Alternative: Using a Python Packaging Tool

You can also use `py2app` to create a proper Mac application bundle:

1. Install py2app:
```bash
pip install py2app
```

2. Create a setup.py file:
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

## For Distribution

Once you have the DMG file, you can distribute it with:
- A download link on your website
- Hosting on a cloud storage service
- Providing it as part of a software suite

## Notes

- The application requires internet connectivity to fetch market data
- Users will need to have Python 3.8+ installed (though the package includes its own Python)
- The first run may take a few moments as dependencies are installed
- The application opens in the user's default browser