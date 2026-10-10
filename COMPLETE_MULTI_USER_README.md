# Francine Screener v2 - Multi-User Web Application

## Complete Solution with Carol User

This package contains everything needed to deploy the Francine Screener v2 as a multi-user web application with 4 user roles including Carol.

## User Roles
1. **Jeffrey** - Administrator role
2. **Tom** - Analyst role  
3. **Francine** - Trader role
4. **Carol** - Research role

## Project Structure

```
.
├── public/
│   ├── login.html          # Authentication page
│   ├── jeffrey.html        # Admin dashboard
│   ├── tom.html            # Analyst dashboard
│   ├── francine.html       # Trader dashboard
│   ├── carol.html          # Research dashboard
│   └── assets/
│       ├── css/
│       │   └── styles.css  # CSS styling
│       └── js/
│           └── auth.js     # Authentication logic
├── src/
│   └── app.py              # Main application logic (Streamlit)
├── requirements.txt        # Python dependencies
├── vercel.json             # Vercel configuration
├── README.md               # This file
└── WEB_DEPLOYMENT_README.md # Web deployment documentation
```

## Deployment Instructions

### 1. Vercel Configuration (vercel.json)
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
    { "src": "/carol", "dest": "/public/carol.html" },
    { "src": "/(.*)", "dest": "/public/index.html" }
  ]
}
```

### 2. User Role Details

#### Jeffrey - Administrator
- Full system access
- User management capabilities
- System monitoring
- Advanced reporting

#### Tom - Analyst
- Detailed screening capabilities
- Data analysis tools
- Report generation
- Research features

#### Francine - Trader
- Quick screening tools
- Portfolio tracking
- Trade execution
- Market insights

#### Carol - Research
- Research-focused interface
- Data mining capabilities
- Advanced analytics
- Custom screening parameters

## Authentication Flow

1. Users visit `/login` page
2. Select their user role (Jeffrey, Tom, Francine, or Carol)
3. Redirected to their personalized dashboard
4. Session maintained during browsing
5. Logout functionality available

## Deployment Steps

1. Fork this repository to your GitHub account
2. Connect your GitHub repository to Vercel
3. Vercel will automatically build and deploy your application
4. Access your deployed application at your Vercel domain

## Running Locally

To test the Streamlit application locally:

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
streamlit run src/app.py
```

## Customization

### Adding New Users
1. Add user to `public/assets/js/auth.js`
2. Create new HTML dashboard page
3. Update `vercel.json` routes

### Modifying Styling
Modify `public/assets/css/styles.css` to customize appearance

## License

MIT License - see LICENSE.txt for details