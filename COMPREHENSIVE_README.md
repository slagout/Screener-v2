# Francine Screener v2 - Complete Package

This is the complete package for the Francine Screener v2 application, which includes both Mac desktop deployment and web deployment options.

## Features

- **Desktop Application**: Mac DMG package for standalone installation
- **Web Application**: Deployable on Vercel with user authentication
- **Three User Roles**: Jeffrey (Admin), Tom (Analyst), Francine (Trader)
- **Institutional Screening**: Uses Francine's updated institutional methodology
- **Responsive Design**: Works on all devices

## Project Structure

```
.
├── public/
│   ├── login.html          # Authentication page
│   ├── jeffrey.html        # Admin dashboard
│   ├── tom.html            # Analyst dashboard
│   ├── francine.html       # Trader dashboard
│   └── assets/
│       ├── css/
│       │   └── styles.css  # CSS styling
│       └── js/
│           └── auth.js     # Authentication logic
├── src/
│   └── app.py              # Main application logic
├── requirements.txt        # Python dependencies
├── vercel.json             # Vercel configuration
├── README.md               # This file
├── LICENSE.txt             # MIT License
└── WEB_DEPLOYMENT_README.md # Web deployment documentation
```

## Desktop Deployment (Mac)

### What's Included
- `FrancineScreener.app` - The main application bundle
- `README.txt` - This file
- `LICENSE.txt` - License information

### Prerequisites
- macOS 10.15 or higher
- Python 3.8 or higher (included in the package)

### Installation
1. Double-click the `FrancineScreener.app` file to launch the application
2. The application will run in your browser automatically

### Usage
1. Launch the application by double-clicking the icon
2. Set your desired parameters in the interface
3. Click "RUN FRANCINE SCREEN v2" to start the screening process

## Web Deployment (Vercel)

### User Roles
1. **Jeffrey** - Administrator role with full access
2. **Tom** - Analyst role with advanced screening capabilities  
3. **Francine** - Trader role with quick screening tools

### Deployment Steps
1. Fork this repository to your GitHub account
2. Connect your GitHub repository to Vercel
3. Vercel will automatically build and deploy your application
4. Access your deployed application at your Vercel domain

### Vercel Configuration
The `vercel.json` file contains all necessary configuration for Vercel deployment:

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
    { "src": "/login", "dest": "/public/login.html" },
    { "src": "/jeffrey", "dest": "/public/jeffrey.html" },
    { "src": "/tom", "dest": "/public/tom.html" },
    { "src": "/francine", "dest": "/public/francine.html" },
    { "src": "/(.*)", "dest": "/public/index.html" }
  ]
}
```

## Requirements

The application requires the following dependencies:
- streamlit
- yfinance
- pandas
- numpy
- requests
- altair

These are included in the package.

## Development

### Running Locally
To test the Streamlit application locally:

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
streamlit run src/app.py
```

### Customizing
#### Adding New Users
1. Add user to `public/assets/js/auth.js`
2. Create new HTML dashboard page
3. Update `vercel.json` routes

#### Styling
Modify `public/assets/css/styles.css` to customize appearance

## License

MIT License - see LICENSE.txt for details

## Support

If you encounter any issues, please refer to the documentation or contact support.