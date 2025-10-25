#!/bin/bash
# Wrapper script to ensure proper URL handling in Docker

echo "🚀 Starting RTSP Consumer with URL: $RTSP_URL"

# Validate URL
if [[ -z "$RTSP_URL" ]]; then
    echo "❌ RTSP_URL environment variable not set"
    exit 1
fi

if [[ ! "$RTSP_URL" =~ ^(rtsp|udp):// ]]; then
    echo "❌ Invalid URL format: $RTSP_URL"
    echo "Expected format: rtsp://host:port/path or udp://host:port"
    exit 1
fi

echo "✅ URL validation passed: $RTSP_URL"

# Run the consumer with the validated URL
# Use exec to replace the shell process and avoid argument passing issues
# Pass the URL as an environment variable to avoid argument parsing issues
export RTSP_URL="$RTSP_URL"
exec python3 rtsp_consumer.py
