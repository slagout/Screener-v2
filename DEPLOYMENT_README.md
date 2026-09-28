# Francine Screener v2 - Web Deployment

This repository contains the complete deployment configuration for running the Francine Screener v2 as a web application on Vercel with user authentication.

## Features

- Deployed as a static web application on Vercel
- Three user roles: Jeffrey, Tom, and Francine
- Login page with role-based access
- Secure authentication flow
- Responsive web interface
- Ready for production deployment

## User Roles

1. **Jeffrey** - Administrator role
2. **Tom** - Analyst role  
3. **Francine** - Trader role

## Deployment Instructions

### 1. Setup Vercel Project

1. Fork this repository
2. Connect to Vercel
3. Configure environment variables
4. Deploy

### 2. Project Structure

```
.
├── public/
│   ├── login.html
│   ├── jeffrey.html
│   ├── tom.html
│   ├── francine.html
│   └── assets/
│       ├── css/
│       │   └── styles.css
│       └── js/
│           └── auth.js
├── src/
│   └── app.py         # Main application logic
├── requirements.txt   # Python dependencies
├── vercel.json        # Vercel configuration
└── README.md
```

## Authentication Flow

1. Users visit `/login.html`
2. Select their role (Jeffrey, Tom, or Francine)
3. Redirected to their respective dashboard
4. Session maintained during browsing

## Vercel Configuration

### vercel.json
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

## User Dashboards

### Jeffrey Dashboard
- Full administrative access
- All screening capabilities
- User management
- System monitoring

### Tom Dashboard  
- Analyst access
- Advanced screening options
- Data export capabilities

### Francine Dashboard
- Trader-focused interface
- Quick screening tools
- Portfolio tracking