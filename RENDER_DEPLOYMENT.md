# Deploying to Render.com with Docker

This guide will help you deploy your tracker app to Render.com using the provided Docker setup.

## Prerequisites

- A Render.com account
- Your AWS credentials and DynamoDB table configured
- Git repository with your code

## Deployment Steps

### 1. Push Your Code

Make sure your code is committed and pushed to your Git repository:

```bash
git add .
git commit -m "Add Docker support for Render deployment"
git push origin main
```

### 2. Create a New Web Service on Render

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click "New +" and select "Web Service"
3. Connect your Git repository
4. Select the repository containing your code

### 3. Configure the Web Service

- **Name**: `tracker` (or your preferred name)
- **Environment**: `Docker`
- **Branch**: `main` (or your default branch)
- **Root Directory**: Leave empty (root of repository)
- **Build Command**: Leave empty (Docker will handle this)
- **Start Command**: Leave empty (Docker CMD will handle this)

### 4. Set Environment Variables

Add these environment variables in the Render dashboard:

- `AWS_ACCESS_KEY_ID`: Your AWS access key
- `AWS_SECRET_ACCESS_KEY`: Your AWS secret key
- `AWS_REGION`: Your AWS region (e.g., `us-east-1`)
- `DYNAMODB_TABLE`: Your DynamoDB table name
- `FLASK_ENV`: `production`

### 5. Deploy

Click "Create Web Service" and Render will:
1. Pull your code
2. Build the Docker image
3. Deploy your application

## Docker Configuration Details

The Dockerfile is configured for production use:

- **Base Image**: Python 3.11 slim for smaller size
- **Port**: Exposes port 8000
- **WSGI Server**: Uses Gunicorn with 2 workers
- **Security**: Runs as non-root user
- **Health Check**: Includes health check endpoint

## Environment Variables

Make sure these are set in your Render environment:

```bash
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1
DYNAMODB_TABLE=tracker
FLASK_ENV=production
```

## Testing

After deployment, your app will be available at:
`https://your-service-name.onrender.com`

## Troubleshooting

### Common Issues

1. **Build Failures**: Check the build logs in Render dashboard
2. **Environment Variables**: Ensure all required AWS credentials are set
3. **Port Issues**: The app runs on port 8000 internally, Render handles external routing

### Viewing Logs

- Go to your service in Render dashboard
- Click on "Logs" tab to view real-time logs
- Check both build and runtime logs for issues

## Updating Your App

To update your deployed app:

1. Make changes to your code
2. Commit and push to your repository
3. Render will automatically rebuild and redeploy

## Cost Considerations

- Render offers a free tier for web services
- Free tier has limitations on build time and runtime
- Consider upgrading for production use

## Security Notes

- Never commit `.env` files with real credentials
- Use Render's environment variable system for secrets
- The Docker image runs as a non-root user for security
