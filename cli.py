#!/usr/bin/env python3
"""
Tracker CLI Tool
Command-line interface for modifying day statuses directly in DynamoDB.
"""

import argparse
import boto3
import json
from datetime import datetime, date, timedelta
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# DynamoDB configuration
dynamodb = boto3.resource('dynamodb',
    region_name=os.getenv('AWS_REGION', 'us-east-1'),
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
)

# Table name for storing marked days
TABLE_NAME = os.getenv('DYNAMODB_TABLE', 'tracker')

def get_marked_days():
    """Fetch all marked days from DynamoDB"""
    try:
        table = dynamodb.Table(TABLE_NAME)
        response = table.scan()
        
        marked_days = {}
        for item in response['Items']:
            marked_days[item['date']] = item['status']
        
        return marked_days
    except Exception as e:
        print(f"Error fetching marked days: {e}")
        return {}

def mark_day(target_date, status):
    """Mark a specific day with the given status in DynamoDB"""
    try:
        table = dynamodb.Table(TABLE_NAME)
        
        if status == 'unset':
            # Remove the item from DynamoDB
            table.delete_item(
                Key={'date': target_date}
            )
            print(f"✅ Successfully removed marking for {target_date}")
        else:
            # Add or update the item
            table.put_item(
                Item={
                    'date': target_date,
                    'status': status,
                    'timestamp': datetime.utcnow().isoformat()
                }
            )
            print(f"✅ Successfully marked {target_date} as {status}")
        
        return True
        
    except Exception as e:
        print(f"Error marking day: {e}")
        return False

def show_calendar():
    """Display a simple calendar view of marked days"""
    marked_days = get_marked_days()
    
    if not marked_days:
        print("No marked days found.")
        return
    
    print("\n📅 Marked Days Calendar:")
    print("=" * 50)
    
    # Group by month
    months = {}
    for day_str, status in marked_days.items():
        try:
            day_date = datetime.strptime(day_str, '%Y-%m-%d').date()
            month_key = f"{day_date.year}-{day_date.month:02d}"
            if month_key not in months:
                months[month_key] = []
            months[month_key].append((day_date.day, status))
        except ValueError:
            continue
    
    # Sort months and display
    for month_key in sorted(months.keys()):
        year, month = month_key.split('-')
        month_name = datetime.strptime(month_key, '%Y-%m').strftime('%B %Y')
        print(f"\n{month_name}:")
        
        # Sort days in the month
        days = sorted(months[month_key], key=lambda x: x[0])
        
        for day, status in days:
            status_icon = "✅" if status == "successful" else "❌"
            print(f"  {day:2d}: {status_icon} {status}")

def show_status():
    """Show current streak and statistics"""
    marked_days = get_marked_days()
    
    if not marked_days:
        print("\n📊 Current Status:")
        print("Days Strong: 0")
        print("Total Marked Days: 0")
        return
    
    successful_days = sum(1 for status in marked_days.values() if status == 'successful')
    unsuccessful_days = sum(1 for status in marked_days.values() if status == 'unsuccessful')
    
    print(f"\n📊 Current Status:")
    print(f"Days Strong: {successful_days}")
    print(f"Unsuccessful Days: {unsuccessful_days}")
    print(f"Total Marked Days: {len(marked_days)}")
    
    # Calculate current streak
    if successful_days > 0:
        # Get the most recent successful day
        successful_dates = [date_str for date_str, status in marked_days.items() if status == 'successful']
        successful_dates.sort()
        
        if successful_dates:
            latest_successful = datetime.strptime(successful_dates[-1], '%Y-%m-%d').date()
            today = date.today()
            
            if latest_successful == today:
                print(f"Current Streak: Today!")
            elif latest_successful == today - timedelta(days=1):
                print(f"Current Streak: Yesterday")
            else:
                days_since = (today - latest_successful).days
                print(f"Last Successful Day: {days_since} days ago")

def main():
    parser = argparse.ArgumentParser(
        description="Tracker CLI - Modify day statuses directly in DynamoDB",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py mark 2024-01-15 successful    # Mark day as successful
  python cli.py mark 2024-01-16 unsuccessful  # Mark day as unsuccessful
  python cli.py mark 2024-01-17 unset        # Remove day marking
  python cli.py show                          # Show calendar view
  python cli.py status                        # Show current streak status
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Mark command
    mark_parser = subparsers.add_parser('mark', help='Mark a day with a status')
    mark_parser.add_argument('date', help='Date in YYYY-MM-DD format')
    mark_parser.add_argument('status', choices=['successful', 'unsuccessful', 'unset'], 
                           help='Status to assign to the day')
    
    # Show command
    subparsers.add_parser('show', help='Show calendar view of marked days')
    
    # Status command
    subparsers.add_parser('status', help='Show current streak status')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == 'mark':
        # Validate date format
        try:
            datetime.strptime(args.date, '%Y-%m-%d')
        except ValueError:
            print("Error: Date must be in YYYY-MM-DD format")
            sys.exit(1)
        
        # Mark the day
        success = mark_day(args.date, args.status)
        if not success:
            sys.exit(1)
    
    elif args.command == 'show':
        show_calendar()
    
    elif args.command == 'status':
        show_status()

if __name__ == '__main__':
    main()
