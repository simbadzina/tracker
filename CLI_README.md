# Tracker CLI Tool

A command-line interface for modifying day statuses directly in DynamoDB.

## Features

- ✅ **Mark Days**: Set days as successful, unsuccessful, or unset
- 📊 **View Calendar**: See all marked days in a calendar format
- 📈 **Check Status**: View current streak and statistics
- 🔐 **Secure**: Direct DynamoDB access with AWS credentials

## Installation

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set Environment Variables**:
   Create a `.env` file with:
   ```
   AWS_REGION=us-east-1
   AWS_ACCESS_KEY_ID=your_access_key_here
   AWS_SECRET_ACCESS_KEY=your_secret_key_here
   DYNAMODB_TABLE=tracker
   ```

## Usage

### Mark a Day
```bash
# Mark a day as successful
python cli.py mark 2024-01-15 successful

# Mark a day as unsuccessful
python cli.py mark 2024-01-16 unsuccessful

# Remove a day's marking
python cli.py mark 2024-01-17 unset
```

### View Information
```bash
# Show calendar view of all marked days
python cli.py show

# Show current streak status
python cli.py status

# Show help
python cli.py --help
```

## Commands

| Command | Description | Example |
|---------|-------------|---------|
| `mark <date> <status>` | Mark a specific date | `mark 2024-01-15 successful` |
| `show` | Display calendar view | `show` |
| `status` | Show current statistics | `status` |

## Status Values

- **`successful`**: Day was successful (green in calendar)
- **`unsuccessful`**: Day was unsuccessful (red in calendar)  
- **`unset`**: Remove day marking (neutral in calendar)

## Date Format

Dates must be in **YYYY-MM-DD** format:
- ✅ `2024-01-15`
- ✅ `2024-12-31`
- ❌ `01/15/2024`
- ❌ `15-01-2024`

## Security

- **AWS Credentials**: Uses your AWS access keys for DynamoDB access
- **Environment Variables**: Store credentials securely in `.env` file
- **Never Share**: Keep your AWS credentials secret and secure
- **IAM Permissions**: Ensure your AWS user has appropriate DynamoDB permissions

## Examples

### Mark Today as Successful
```bash
python cli.py mark $(date +%Y-%m-%d) successful
```

### Mark Yesterday as Unsuccessful
```bash
python cli.py mark $(date -d "yesterday" +%Y-%m-%d) unsuccessful
```

### View Your Progress
```bash
python cli.py show
python cli.py status
```

## Troubleshooting

### "Access Denied" or "Unauthorized"
- Ensure you have a `.env` file with AWS credentials
- Check that `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are set
- Verify your AWS user has DynamoDB permissions
- Restart your terminal after creating `.env`

### "Table not found"
- Ensure the DynamoDB table exists
- Check that `DYNAMODB_TABLE` is set correctly in `.env`
- Verify the table name matches exactly

### "Region not found"
- Check that `AWS_REGION` is set correctly
- Ensure the region exists and is accessible
