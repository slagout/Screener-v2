// Francine Screener - Authentication Script

// User data (in production, this would be server-side)
const users = {
    jeffrey: {
        name: "Jeffrey",
        role: "administrator",
        password: "admin123"
    },
    tom: {
        name: "Tom",
        role: "analyst",
        password: "analyst123"
    },
    francine: {
        name: "Francine",
        role: "trader",
        password: "trader123"
    }
};

// Handle user selection
function selectUser(userRole) {
    // Store selected user in localStorage
    localStorage.setItem('currentUser', userRole);
    
    // Redirect to user dashboard
    window.location.href = '/' + userRole;
}

// Check if user is authenticated
function checkAuthentication() {
    const currentUser = localStorage.getItem('currentUser');
    
    // If not authenticated and not on login page, redirect to login
    if (!currentUser && window.location.pathname !== '/login') {
        window.location.href = '/login';
        return;
    }
    
    // If authenticated but on login page, redirect to dashboard
    if (currentUser && window.location.pathname === '/login') {
        window.location.href = '/' + currentUser;
        return;
    }
    
    // Update header with user info
    if (currentUser) {
        const user = users[currentUser];
        if (user) {
            document.querySelector('.user-name').textContent = user.name;
        }
    }
}

// Initialize authentication
document.addEventListener('DOMContentLoaded', function() {
    checkAuthentication();
});

// Logout function
function logout() {
    localStorage.removeItem('currentUser');
    window.location.href = '/login';
}