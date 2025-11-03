from flask import Flask, render_template, jsonify
from datetime import datetime, date, timedelta
import calendar
import boto3
import os
from dotenv import load_dotenv
from functools import lru_cache
import json

# Load environment variables
load_dotenv()

app = Flask(__name__)

# DynamoDB configuration
dynamodb = boto3.resource('dynamodb',
    region_name=os.getenv('AWS_REGION', 'us-east-1'),
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
)

# Table name for storing marked days
TABLE_NAME = os.getenv('DYNAMODB_TABLE', 'tracker')

# Admin page path (configurable via environment variable)
ADMIN_PATH = os.getenv('ADMIN_PATH')

# Start date for the streak
START_DATE = date(2025, 8, 26)

# Check if admin path is configured
if not ADMIN_PATH:
    raise ValueError("ADMIN_PATH environment variable must be set")

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
    
    # Show months up to current month only, in reverse order (latest first)
    for i in range(months_to_show - 1, -1, -1):
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
    return render_template('index.html')

def admin():
    return render_template('admin.html')

# Register the admin route dynamically
app.add_url_rule(f'/{ADMIN_PATH}', 'admin', admin)

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
def toggle_day():
    """Toggle the state of a specific day"""
    from flask import request
    
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
        
        # Invalidate cache after data modification
        invalidate_cache()
        
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
