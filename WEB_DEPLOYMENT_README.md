# Francine Screener v2 - Web Deployment Package

This package contains everything needed to deploy the Francine Screener v2 as a web application on Vercel with user authentication for Jeffrey, Tom, and Francine.

## Features

- Static web application deployment on Vercel
- Three user roles with dedicated dashboards
- Secure authentication flow
- Responsive design for all devices
- Ready for production deployment

## Project Structure

```
.
├── public/
│   ├── login.html          # Login page
│   ├── jeffrey.html        # Jeffrey's dashboard
│   ├── tom.html            # Tom's dashboard  
│   ├── francine.html       # Francine's dashboard
│   └── assets/
│       ├── css/
│       │   └── styles.css  # Styling
│       └── js/
│           └── auth.js     # Authentication logic
├── src/
│   └── app.py              # Main application logic (Streamlit)
├── requirements.txt        # Python dependencies
├── vercel.json             # Vercel configuration
└── README.md               # This file
```

## User Roles

1. **Jeffrey** - Administrator role with full access
2. **Tom** - Analyst role with advanced screening capabilities  
3. **Francine** - Trader role with quick screening tools

## Vercel Deployment

### 1. vercel.json Configuration
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

### 2. Deployment Steps

1. Fork this repository
2. Connect to Vercel
3. Configure environment variables (if needed)
4. Deploy with automatic build

## Authentication Flow

1. Users visit `/login` page
2. Select their role (Jeffrey, Tom, or Francine)
3. Redirected to their respective dashboard
4. Session maintained during browsing
5. Logout functionality available

## Security Considerations

- Client-side authentication (for demo purposes)
- In production, implement server-side authentication
- Passwords are stored locally in this example
- Production deployment requires secure backend implementation

## Running Locally

To test locally:
1. Install Python dependencies: `pip install -r requirements.txt`
2. Run the application: `streamlit run src/app.py`

## Customization

### Adding New Users
1. Add user to `public/assets/js/auth.js`
2. Create new HTML dashboard page
3. Update routing in `vercel.json`

### Modifying Styling
Edit `public/assets/css/styles.css` to customize appearance

## License

MIT License - see LICENSE.txt for details