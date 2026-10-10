# Vercel Deployment Guide for Francine Screener v2

## Issue Analysis
The warnings you're seeing:
- "Due to `builds` existing in your configuration file, the Build and Development Settings defined in your Project Settings will not apply"
- "Build output contains no "functions", "static", or "services" directory"

These indicate Vercel isn't properly building your Python Streamlit application.

## Recommended Solutions

### Solution 1: Use Streamlit Cloud (Easiest)
1. Go to https://streamlit.io/cloud
2. Create a new app
3. Connect your GitHub repository
4. Set the build command to: `pip install -r requirements.txt && streamlit run src/app.py`
5. Set the port to: 8501
6. Deploy!

### Solution 2: Fix Vercel Configuration
If you want to stick with Vercel, here's the correct approach:

1. **Update your requirements.txt** to include streamlit:
```
streamlit==1.40.2
yfinance==0.2.54
pandas==2.2.3
numpy==2.0.2
requests==2.32.3
altair==5.5.0
```

2. **Fix your vercel.json**:
```json
{
  "version": 2,
  "builds": [
    {
      "src": "src/app.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    { "src": "/(.*)", "dest": "/src/app.py" }
  ]
}
```

3. **Ensure your app.py is properly structured** for web deployment.

## Alternative Approach: Use a Different Platform

Consider using:
- **Render.com** - Great for Python web apps
- **Fly.io** - Good for Python applications
- **Heroku** - Traditional platform for Python apps

## Immediate Fix for Your Current Deployment

1. **Check your current deployment**: 
   - The URL https://screener-v2-seven.vercel.app/ is showing a 404
   - This means your build failed or wasn't properly configured

2. **Steps to fix**:
   - Delete the current Vercel project
   - Recreate with correct configuration
   - Make sure your GitHub repo is properly connected
   - Ensure the build command is correct

## What You Should Do Now

1. **Go to Vercel Dashboard** (https://vercel.com/dashboard)
2. **Delete the current project** (if it exists)
3. **Reconnect your GitHub repository**
4. **Use the correct vercel.json configuration** shown above
5. **Set the build command** to: `pip install -r requirements.txt && streamlit run src/app.py`
6. **Deploy again**

## Important Notes

- Vercel is primarily designed for static sites and serverless functions
- Streamlit apps are web applications that need to run continuously
- For a true Streamlit deployment, consider Streamlit Cloud or a proper Python hosting platform