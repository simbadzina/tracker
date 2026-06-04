from flask import Flask, render_template, jsonify, session, redirect, request, url_for
from werkzeug.middleware.proxy_fix import ProxyFix
from datetime import datetime, date, timedelta
import calendar
import boto3
import os
import secrets
import requests
from dotenv import load_dotenv
from functools import lru_cache, wraps
import json

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Behind one reverse proxy (Caddy on the Pi). Trust X-Forwarded-Proto/Host so Flask builds
# https URLs and marks the session cookie correctly.
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Session / cookie config for the Google-login flow
app.secret_key = os.getenv('SECRET_KEY', 'dev-only-insecure-key-change-me')
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
)

# Google OAuth (OIDC) configuration
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:5000/callback')
GOOGLE_AUTH_ENDPOINT = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_ENDPOINT = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_ENDPOINT = 'https://www.googleapis.com/oauth2/v2/userinfo'

# Allowlist of Google accounts permitted to edit (comma-separated emails, case-insensitive)
ALLOWED_EMAILS = {
    e.strip().lower() for e in os.getenv('ALLOWED_EMAILS', '').split(',') if e.strip()
}


def current_email():
    """Email of the signed-in user, or None."""
    return session.get('email')


def is_admin():
    """True when the signed-in user is on the allowlist (i.e. may edit)."""
    email = current_email()
    return bool(email) and email.lower() in ALLOWED_EMAILS


def admin_required(f):
    """Guard write endpoints: 401 JSON unless the session is an allowed account."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not is_admin():
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return wrapper

# DynamoDB configuration
dynamodb = boto3.resource('dynamodb',
    region_name=os.getenv('AWS_REGION', 'us-east-1'),
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
)

# Table name for storing marked days
TABLE_NAME = os.getenv('DYNAMODB_TABLE', 'tracker')

# Start date for the streak
START_DATE = date(2026, 6, 1)

# Cache for marked days data (in-memory cache with TTL)
_marked_days_cache = {}
_cache_ttl = 30  # seconds
_cache_timestamp = 0

def get_cached_marked_days():
    """Get marked days from cache or database with TTL"""
    global _marked_days_cache, _cache_timestamp
    
    current_time = datetime.now().timestamp()
    
    # Check if cache is still valid
    if current_time - _cache_timestamp < _cache_ttl and _marked_days_cache:
        return _marked_days_cache
    
    # Cache expired or empty, fetch from database
    try:
        table = dynamodb.Table(TABLE_NAME)
        response = table.scan()
        
        _marked_days_cache = {}
        for item in response['Items']:
            _marked_days_cache[item['date']] = item['status']
        
        _cache_timestamp = current_time
        return _marked_days_cache
    except Exception as e:
        print(f"Error getting marked days: {e}")
        return {}

@lru_cache(maxsize=32)
def get_calendar_data(today_key):
    """Cache calendar data generation (only changes once per day)
    today_key is a string representation of today's date for cache invalidation"""
    months_data = []
    start_year = START_DATE.year
    start_month = START_DATE.month  # August = 8
    
    # Get current date to limit calendar display
    today = date.today()
    current_year = today.year
    current_month = today.month
    
    # Calculate how many months to show (from start month to current month)
    if current_year > start_year:
        # If we're in a different year, calculate total months
        months_to_show = (current_year - start_year) * 12 + (current_month - start_month) + 1
    else:
        # If we're in the same year
        months_to_show = current_month - start_month + 1
    
    # Ensure we show at least 1 month
    months_to_show = max(1, months_to_show)
    
    # Show months up to current month only
    for i in range(0, months_to_show):
        # Calculate the year and month for this iteration
        year = start_year + ((start_month + i - 1) // 12)
        month = ((start_month + i - 1) % 12) + 1
        
        cal = calendar.monthcalendar(year, month)
        month_name = calendar.month_name[month]
        
        months_data.append({
            'year': year,
            'month': month,
            'month_name': month_name,
            'calendar': cal,
            'start_date': date(year, month, 1),
            'end_date': date(year, month, calendar.monthrange(year, month)[1])
        })
    
    return months_data

@app.route('/')
def index():
    # is_admin drives whether the page renders the calendar as editable.
    return render_template('index.html', is_admin=is_admin())


@app.route('/login')
def login():
    if not GOOGLE_CLIENT_ID:
        return 'Google login is not configured (set GOOGLE_CLIENT_ID).', 503
    state = secrets.token_urlsafe(16)
    session['oauth_state'] = state
    auth_url = (
        f'{GOOGLE_AUTH_ENDPOINT}?response_type=code'
        f'&client_id={GOOGLE_CLIENT_ID}'
        f'&redirect_uri={GOOGLE_REDIRECT_URI}'
        '&scope=openid%20email'
        '&prompt=select_account'
        f'&state={state}'
    )
    return redirect(auth_url)


@app.route('/callback')
def callback():
    # CSRF protection: the state must match what we issued in /login.
    if not request.args.get('state') or request.args.get('state') != session.pop('oauth_state', None):
        return 'Invalid OAuth state', 400

    code = request.args.get('code')
    if not code:
        return redirect(url_for('index'))

    # Exchange the authorization code for tokens, server-to-server over TLS.
    token_resp = requests.post(GOOGLE_TOKEN_ENDPOINT, data={
        'client_id': GOOGLE_CLIENT_ID,
        'client_secret': GOOGLE_CLIENT_SECRET,
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': GOOGLE_REDIRECT_URI,
    }, timeout=10)
    if token_resp.status_code != 200:
        return 'Failed to exchange authorization code', 400

    access_token = token_resp.json().get('access_token')
    if not access_token:
        return 'No access token returned', 400

    # The token came directly from Google over TLS, so the userinfo it unlocks is trusted.
    userinfo_resp = requests.get(
        GOOGLE_USERINFO_ENDPOINT,
        headers={'Authorization': f'Bearer {access_token}'},
        timeout=10,
    )
    if userinfo_resp.status_code != 200:
        return 'Failed to fetch user info', 400

    email = (userinfo_resp.json().get('email') or '').lower()
    if email not in ALLOWED_EMAILS:
        return 'This Google account is not authorized for this tracker.', 403

    session['email'] = email
    session.permanent = True
    return redirect(url_for('index'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/health')
def health_check():
    """Health check endpoint for Docker and load balancers"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()}), 200

@app.route('/api/streak')
def get_streak():
    today = date.today()
    
    # Calculate days since start
    days_since_start = (today - START_DATE).days
    
    # Get marked days from cache instead of direct DB call
    marked_days = get_cached_marked_days()
    
    # Calculate current streak and success rate based on marked days
    current_streak = 0
    successful_days = 0
    unsuccessful_days = 0
    
    if days_since_start >= 0:
        today_str = today.strftime('%Y-%m-%d')
        
        # Count successful and unsuccessful days
        current_date = START_DATE
        while current_date <= today:
            date_str = current_date.strftime('%Y-%m-%d')
            
            if date_str in marked_days:
                if marked_days[date_str] == 'successful':
                    successful_days += 1
                elif marked_days[date_str] == 'unsuccessful':
                    unsuccessful_days += 1
            
            current_date += timedelta(days=1)
        
        # Find the most recent successful day (but only up to today)
        most_recent_success = None
        current_date = today
        
        # Look backwards from today to find the most recent successful day
        while current_date >= START_DATE:
            date_str = current_date.strftime('%Y-%m-%d')
            
            if date_str in marked_days:
                if marked_days[date_str] == 'successful':
                    most_recent_success = current_date
                    break
                elif marked_days[date_str] == 'unsuccessful':
                    # If we hit an unsuccessful day, streak is broken
                    break
            
            current_date -= timedelta(days=1)
        
        if most_recent_success:
            # Calculate streak from the most recent successful day backwards
            # But only count days up to today (don't count future dates)
            streak_date = most_recent_success
            while streak_date >= START_DATE and streak_date <= today:
                date_str = streak_date.strftime('%Y-%m-%d')
                
                if date_str in marked_days:
                    if marked_days[date_str] == 'successful':
                        current_streak += 1
                    elif marked_days[date_str] == 'unsuccessful':
                        # If we hit an unsuccessful day, streak is broken
                        break
                else:
                    # If day is not marked, don't assume it's a failure
                    # Just stop counting (this preserves partial streaks)
                    break
                
                streak_date -= timedelta(days=1)
    
    # Calculate success rate percentage
    total_marked_days = successful_days + unsuccessful_days
    if total_marked_days > 0:
        success_rate = round((successful_days / total_marked_days) * 100, 1)
    else:
        success_rate = 0.0
    
    # Get cached calendar data (pass today's date as cache key)
    months_data = get_calendar_data(today.strftime('%Y-%m-%d'))
    
    return jsonify({
        'start_date': START_DATE.strftime('%Y-%m-%d'),
        'current_streak': current_streak,
        'days_since_start': days_since_start,
        'success_rate': success_rate,
        'successful_days': successful_days,
        'unsuccessful_days': unsuccessful_days,
        'total_marked_days': total_marked_days,
        'months_data': months_data,
        'today': today.strftime('%Y-%m-%d'),
        'marked_days': marked_days  # Include marked days in response to avoid second API call
    })

@app.route('/api/marked-days', methods=['GET'])
def get_marked_days():
    """Get all marked days from cache (read-only)"""
    try:
        marked_days = get_cached_marked_days()
        return jsonify(marked_days)
    except Exception as e:
        print(f"Error getting marked days: {e}")
        return jsonify({}), 500

def invalidate_cache():
    """Invalidate the marked days cache"""
    global _marked_days_cache, _cache_timestamp
    _marked_days_cache = {}
    _cache_timestamp = 0

@app.route('/api/toggle-day', methods=['POST'])
@admin_required
def toggle_day():
    """Toggle the state of a specific day (requires an allowed Google account)"""
    try:
        data = request.get_json()
        date_str = data.get('date')
        current_status = data.get('current_status', 'unmarked')
        
        if not date_str:
            return jsonify({'error': 'Date is required'}), 400
        
        # Validate date format
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
        table = dynamodb.Table(TABLE_NAME)
        
        # Determine next status based on current status
        if current_status == 'unmarked':
            next_status = 'successful'
        elif current_status == 'successful':
            next_status = 'unsuccessful'
        elif current_status == 'unsuccessful':
            next_status = 'unmarked'
        else:
            next_status = 'successful'  # Default fallback
        
        if next_status == 'unmarked':
            # Remove the item from DynamoDB
            try:
                table.delete_item(Key={'date': date_str})
            except Exception as e:
                print(f"Error deleting item: {e}")
                # Continue even if delete fails (item might not exist)
        else:
            # Add or update the item in DynamoDB
            table.put_item(Item={
                'date': date_str,
                'status': next_status,
                'updated_at': datetime.now().isoformat()
            })
        
        # Keep the in-memory cache warm by applying just this one change, so the follow-up
        # stats refresh reads from cache instead of triggering a slow full DynamoDB re-scan.
        global _cache_timestamp
        cache = get_cached_marked_days()
        if next_status == 'unmarked':
            cache.pop(date_str, None)
        else:
            cache[date_str] = next_status
        _cache_timestamp = datetime.now().timestamp()

        return jsonify({
            'date': date_str,
            'status': next_status,
            'message': f'Day {date_str} set to {next_status}'
        })
        
    except Exception as e:
        print(f"Error toggling day: {e}")
        return jsonify({'error': 'Failed to toggle day'}), 500

if __name__ == '__main__':
    app.run(debug=True)
