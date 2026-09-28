#!/bin/bash

# Francine Screener v2 - Mac Installer Script

echo "Installing Francine Screener v2 for Mac..."
echo "=========================================="

# Create application directory structure
mkdir -p /Applications/FrancineScreener.app/Contents/MacOS
mkdir -p /Applications/FrancineScreener.app/Contents/Resources

# Copy application files
cp ./app.py /Applications/FrancineScreener.app/Contents/MacOS/
cp ./requirements.txt /Applications/FrancineScreener.app/Contents/MacOS/

# Create Info.plist
cat > /Applications/FrancineScreener.app/Contents/Info.plist << EOF
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
EOF

# Create launcher script
cat > /Applications/FrancineScreener.app/Contents/MacOS/run_app << 'EOF'
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
EOF

chmod +x /Applications/FrancineScreener.app/Contents/MacOS/run_app

echo "Installation complete!"
echo ""
echo "To run the application:"
echo "1. Open Finder"
echo "2. Navigate to /Applications/FrancineScreener.app"
echo "3. Double-click the FrancineScreener icon"