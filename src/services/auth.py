"""
Optional authentication system for GitHub Followers Tracker.
Provides basic authentication when enabled via configuration.
"""
import os
import hashlib
import secrets
import logging
from functools import wraps
from datetime import datetime, timedelta
from typing import Optional, Callable

from flask import request, jsonify, session, redirect, url_for, g

logger = logging.getLogger(__name__)

# Authentication configuration
AUTH_ENABLED = os.getenv('GFT_AUTH_ENABLED', 'false').lower() == 'true'
AUTH_USERNAME = os.getenv('GFT_AUTH_USERNAME', 'admin')
AUTH_PASSWORD_HASH = os.getenv('GFT_AUTH_PASSWORD_HASH', '')
AUTH_SECRET_KEY = os.getenv('GFT_SECRET_KEY', secrets.token_hex(32))
SESSION_LIFETIME_HOURS = int(os.getenv('GFT_SESSION_LIFETIME', '24'))

# API token for programmatic access
API_TOKEN = os.getenv('GFT_API_TOKEN', '')


def hash_password(password: str) -> str:
    """
    Hash a password using SHA-256 with salt.

    For production, consider using bcrypt or argon2.
    """
    salt = os.getenv('GFT_PASSWORD_SALT', 'gft_default_salt')
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    return hash_password(password) == password_hash


def generate_api_token() -> str:
    """Generate a secure API token."""
    return secrets.token_urlsafe(32)


class AuthService:
    """
    Authentication service for the application.

    Usage:
        auth = AuthService(app)

        @app.route('/protected')
        @auth.login_required
        def protected_route():
            return 'Secret data'
    """

    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)

    def init_app(self, app):
        """Initialize authentication with Flask app."""
        self.app = app

        # Set secret key for sessions
        app.secret_key = AUTH_SECRET_KEY

        # Configure session
        app.config['SESSION_TYPE'] = 'filesystem'
        app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=SESSION_LIFETIME_HOURS)

        # Register before_request handler
        @app.before_request
        def check_auth():
            """Check authentication before each request."""
            g.user = None
            g.auth_enabled = AUTH_ENABLED

            if not AUTH_ENABLED:
                g.user = {'username': 'anonymous', 'authenticated': True}
                return

            # Check session
            if 'user' in session:
                g.user = session['user']
                return

            # Check API token in header
            token = request.headers.get('X-API-Token')
            if token and API_TOKEN and token == API_TOKEN:
                g.user = {'username': 'api', 'authenticated': True}
                return

            # Check Basic Auth
            auth = request.authorization
            if auth:
                if self.verify_credentials(auth.username, auth.password):
                    g.user = {'username': auth.username, 'authenticated': True}
                    return

    def verify_credentials(self, username: str, password: str) -> bool:
        """Verify username and password."""
        if username != AUTH_USERNAME:
            return False

        if AUTH_PASSWORD_HASH:
            return verify_password(password, AUTH_PASSWORD_HASH)

        # If no hash is set, accept any password (for development)
        logger.warning("No password hash set - accepting any password")
        return True

    def login_required(self, f: Callable) -> Callable:
        """
        Decorator to require authentication for a route.

        Usage:
            @app.route('/protected')
            @auth.login_required
            def protected():
                return 'Secret'
        """
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not AUTH_ENABLED:
                return f(*args, **kwargs)

            if g.user and g.user.get('authenticated'):
                return f(*args, **kwargs)

            # Check if it's an API request
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401

            # Redirect to login page
            return redirect(url_for('auth.login', next=request.url))

        return decorated_function

    def api_token_required(self, f: Callable) -> Callable:
        """
        Decorator to require API token for a route.

        Usage:
            @app.route('/api/data')
            @auth.api_token_required
            def api_data():
                return {'data': 'secret'}
        """
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not AUTH_ENABLED:
                return f(*args, **kwargs)

            token = request.headers.get('X-API-Token')
            if not token:
                return jsonify({'error': 'API token required'}), 401

            if not API_TOKEN:
                logger.warning("No API token configured")
                return jsonify({'error': 'API token not configured'}), 500

            if token != API_TOKEN:
                return jsonify({'error': 'Invalid API token'}), 401

            return f(*args, **kwargs)

        return decorated_function


# Create authentication blueprint for login/logout routes
from flask import Blueprint

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page and handler."""
    if not AUTH_ENABLED:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')

        if username == AUTH_USERNAME:
            if AUTH_PASSWORD_HASH:
                if verify_password(password, AUTH_PASSWORD_HASH):
                    session['user'] = {'username': username, 'authenticated': True}
                    session.permanent = True
                    next_url = request.args.get('next', url_for('index'))
                    return redirect(next_url)
            else:
                # No password set - allow login (development mode)
                session['user'] = {'username': username, 'authenticated': True}
                session.permanent = True
                return redirect(url_for('index'))

        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Login - GitHub Followers Tracker</title>
            <style>
                body { font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background: #1a1a2e; color: #fff; }
                .login-form { background: #16213e; padding: 2rem; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
                h1 { margin-bottom: 1.5rem; }
                input { display: block; width: 100%; padding: 0.75rem; margin-bottom: 1rem; border: 1px solid #0f3460; border-radius: 4px; background: #1a1a2e; color: #fff; box-sizing: border-box; }
                button { width: 100%; padding: 0.75rem; background: #e94560; border: none; border-radius: 4px; color: #fff; cursor: pointer; font-size: 1rem; }
                button:hover { background: #ff6b6b; }
                .error { color: #e94560; margin-bottom: 1rem; }
            </style>
        </head>
        <body>
            <div class="login-form">
                <h1>Login</h1>
                <p class="error">Invalid credentials</p>
                <form method="post">
                    <input type="text" name="username" placeholder="Username" required>
                    <input type="password" name="password" placeholder="Password" required>
                    <button type="submit">Login</button>
                </form>
            </div>
        </body>
        </html>
        ''', 401

    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Login - GitHub Followers Tracker</title>
        <style>
            body { font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background: #1a1a2e; color: #fff; }
            .login-form { background: #16213e; padding: 2rem; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
            h1 { margin-bottom: 1.5rem; }
            input { display: block; width: 100%; padding: 0.75rem; margin-bottom: 1rem; border: 1px solid #0f3460; border-radius: 4px; background: #1a1a2e; color: #fff; box-sizing: border-box; }
            button { width: 100%; padding: 0.75rem; background: #e94560; border: none; border-radius: 4px; color: #fff; cursor: pointer; font-size: 1rem; }
            button:hover { background: #ff6b6b; }
        </style>
    </head>
    <body>
        <div class="login-form">
            <h1>GitHub Followers Tracker</h1>
            <form method="post">
                <input type="text" name="username" placeholder="Username" required>
                <input type="password" name="password" placeholder="Password" required>
                <button type="submit">Login</button>
            </form>
        </div>
    </body>
    </html>
    '''


@auth_bp.route('/logout')
def logout():
    """Logout handler."""
    session.pop('user', None)
    return redirect(url_for('auth.login'))


@auth_bp.route('/status')
def auth_status():
    """Get authentication status."""
    return jsonify({
        'auth_enabled': AUTH_ENABLED,
        'authenticated': g.user is not None and g.user.get('authenticated', False),
        'username': g.user.get('username') if g.user else None
    })


# Global auth service instance
auth_service = AuthService()


def setup_auth(app):
    """Set up authentication for the Flask app."""
    auth_service.init_app(app)
    app.register_blueprint(auth_bp)
    return auth_service
