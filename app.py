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

@app.route('/api/streak')
def get_streak():
    today = date.today()
    
    # Calculate days since start
    days_since_start = (today - START_DATE).days
    
    # Calculate current streak (days since start)
    # For now, assuming no relapses since start
    current_streak = max(0, days_since_start)
    
    # Get calendar data for the next 12 months starting from August 2025
    months_data = []
    start_year = START_DATE.year
    start_month = START_DATE.month  # August = 8
    
    # Show exactly 12 months
    for i in range(12):
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
