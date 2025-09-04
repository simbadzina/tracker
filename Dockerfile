# Multi-stage build for maximum optimization
FROM python:3.11-alpine AS builder

# Install build dependencies
RUN apk add --no-cache --virtual .build-deps \
        gcc \
        musl-dev

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip cache purge

# Final stage - minimal runtime image
FROM python:3.11-alpine

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV PORT=8000

# Copy only the installed packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . .

# Expose port
EXPOSE $PORT

# Run as root for simplicity (single user deployment)
# Use single worker, minimal timeout, and no logging for fastest startup
CMD gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 10 --preload app:app
