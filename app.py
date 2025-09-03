from flask import Flask, render_template, jsonify
from datetime import datetime, date, timedelta
import calendar
import boto3
import os
from dotenv import load_dotenv

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
    
    # Get marked days from DynamoDB to calculate actual streak
    try:
        table = dynamodb.Table(TABLE_NAME)
        response = table.scan()
        
        marked_days = {}
        for item in response['Items']:
            marked_days[item['date']] = item['status']
        
        # Calculate current streak based on marked days
        current_streak = 0
        if days_since_start >= 0:
            today_str = today.strftime('%Y-%m-%d')
            
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
        
    except Exception as e:
        print(f"Error getting marked days for streak calculation: {e}")
        # Fallback to days since start if DynamoDB fails
        current_streak = max(0, days_since_start)
    
    # Get calendar data for the next 12 months starting from August 2025
    months_data = []
    start_year = START_DATE.year
    start_month = START_DATE.month  # August = 8
    
    # Show exactly 12 months
    for i in range(13):
        # Calculate the year and month for this iteration
        current_year = start_year + ((start_month + i - 1) // 12)
        current_month = ((start_month + i - 1) % 12) + 1
        
        cal = calendar.monthcalendar(current_year, current_month)
        month_name = calendar.month_name[current_month]
        
        months_data.append({
            'year': current_year,
            'month': current_month,
            'month_name': month_name,
            'calendar': cal,
            'start_date': date(current_year, current_month, 1),
            'end_date': date(current_year, current_month, calendar.monthrange(current_year, current_month)[1])
        })
    
    return jsonify({
        'start_date': START_DATE.strftime('%Y-%m-%d'),
        'current_streak': current_streak,
        'days_since_start': days_since_start,
        'months_data': months_data,
        'today': today.strftime('%Y-%m-%d')
    })

@app.route('/api/marked-days', methods=['GET'])
def get_marked_days():
    """Get all marked days from DynamoDB (read-only)"""
    try:
        table = dynamodb.Table(TABLE_NAME)
        response = table.scan()
        
        marked_days = {}
        for item in response['Items']:
            marked_days[item['date']] = item['status']
        
        return jsonify(marked_days)
    except Exception as e:
        print(f"Error getting marked days: {e}")
        return jsonify({}), 500

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
