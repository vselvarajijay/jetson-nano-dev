#!/usr/bin/env python3
"""
Simple test script to verify Docker environment and URL parsing
"""

import os
import sys

def main():
    print("=" * 60)
    print("🧪 DOCKER ENVIRONMENT TEST")
    print("=" * 60)
    
    # Test environment variables
    print(f"🔗 RTSP_URL: {os.getenv('RTSP_URL', 'NOT SET')}")
    print(f"🔗 PYTHONUNBUFFERED: {os.getenv('PYTHONUNBUFFERED', 'NOT SET')}")
    print(f"🔗 GST_DEBUG: {os.getenv('GST_DEBUG', 'NOT SET')}")
    print(f"🔗 Working directory: {os.getcwd()}")
    print(f"🔗 Python version: {sys.version}")
    print(f"🔗 Command line args: {sys.argv}")
    
    # Test URL parsing
    url = os.getenv('RTSP_URL', 'udp://100.94.31.62:8554')
    print(f"🔗 Parsed URL: {url}")
    
    if url.startswith('udp://') or url.startswith('rtsp://'):
        print(f"✅ URL format is valid: {url}")
    else:
        print(f"❌ Invalid URL format: {url}")
    
    print("=" * 60)
    print("✅ Test completed successfully!")
    print("=" * 60)
    sys.stdout.flush()

if __name__ == "__main__":
    main()
