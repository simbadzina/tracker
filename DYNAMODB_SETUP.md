# DynamoDB Setup for Tracker

## Prerequisites
- AWS Account
- AWS CLI configured with appropriate permissions
- Python 3.7+

## Setup Steps

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Create DynamoDB Table
Run this AWS CLI command to create the table:
```bash
aws dynamodb create-table \
    --table-name tracker \
    --attribute-definitions AttributeName=date,AttributeType=S \
    --key-schema AttributeName=date,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region us-east-1
```

### 3. Create Environment File
Create a `.env` file in the project root with:
```
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
DYNAMODB_TABLE=tracker
```

### 4. AWS IAM Permissions
Ensure your AWS user has these DynamoDB permissions:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:UpdateItem",
                "dynamodb:DeleteItem",
                "dynamodb:Scan",
                "dynamodb:Query"
            ],
            "Resource": "arn:aws:dynamodb:*:*:table/tracker"
        }
    ]
}
```

### 5. Run the Application
```bash
python app.py
```

## Table Schema
- **Primary Key**: `date` (String, format: YYYY-MM-DD)
- **Attributes**:
  - `status`: String ("successful" or "unsuccessful")
  - `timestamp`: String (ISO format)

## Features
- ✅ Persistent storage of marked days
- ✅ Real-time streak calculation
- ✅ Scalable cloud database
- ✅ No local storage dependencies
