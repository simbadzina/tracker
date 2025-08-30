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

# Start date for the streak
START_DATE = date(2025, 8, 26)

@app.route('/')
def index():
    return render_template('index.html')

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
            # First check if today is marked - if not marked or marked as failure, streak is 0
            today_str = today.strftime('%Y-%m-%d')
            
            if today_str not in marked_days or marked_days[today_str] == 'failure':
                current_streak = 0
            else:
                # Today is marked as success, so count backwards from yesterday
                current_date = today - timedelta(days=1)
                while current_date >= START_DATE:
                    date_str = current_date.strftime('%Y-%m-%d')
                    
                    if date_str in marked_days:
                        if marked_days[date_str] == 'success':
                            current_streak += 1
                        elif marked_days[date_str] == 'failure':
                            # If we hit a failure, streak is broken
                            break
                    else:
                        # If day is not marked, assume it's a failure (streak broken)
                        break
                    
                    current_date -= timedelta(days=1)
                
                # Add 1 for today since it's marked as success
                current_streak += 1
        
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

if __name__ == '__main__':
    app.run(debug=True)
