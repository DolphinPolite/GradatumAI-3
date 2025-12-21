#!/usr/bin/env python3
"""
Simple video analysis test script
Sends a video analysis request to the running API server
"""

import requests
import json
import time
from pathlib import Path

# API Server configuration
API_BASE_URL = "http://localhost:5000"
VIDEO_PATH = "resources/VideoProject.mp4"

def check_api_health():
    """Check if API server is running"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/health", timeout=2)
        if response.status_code == 200:
            print("✅ API Server is running")
            return True
        else:
            print("❌ API Server returned error")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to API server on http://localhost:5000")
        print("   Make sure api_server.py is running!")
        return False

def analyze_video(video_path):
    """Send video to API for analysis"""
    
    # Check if video exists
    if not Path(video_path).exists():
        print(f"❌ Video not found: {video_path}")
        return None
    
    print(f"\n📹 Video Analysis Request")
    print(f"   File: {video_path}")
    print(f"   Size: {Path(video_path).stat().st_size / (1024*1024):.1f} MB")
    
    # Prepare request
    url = f"{API_BASE_URL}/api/analyze"
    payload = {
        "video_path": str(Path(video_path).absolute()),
        "process_frames": 100  # Process first 100 frames for demo
    }
    
    try:
        print(f"\n🚀 Sending analysis request to {url}")
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code in [200, 202]:  # 200 OK or 202 Accepted
            result = response.json()
            print(f"✅ Analysis started!")
            print(f"   Job ID: {result.get('job_id')}")
            print(f"   Status: {result.get('status')}")
            print(f"   Check status at: {result.get('check_status_at')}")
            return result.get('job_id')
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        print("❌ Request timeout - API might be busy")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def get_analysis_status(job_id):
    """Check analysis status"""
    try:
        url = f"{API_BASE_URL}/api/status"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            status = response.json()
            print(f"\n📊 Analysis Status:")
            print(f"   Processing: {status.get('processing')}")
            print(f"   Progress: {status.get('progress')}%")
            print(f"   Results available: {status.get('results_available')}")
            return status
        else:
            print(f"❌ Error getting status: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def get_api_info():
    """Get API information"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/info", timeout=5)
        if response.status_code == 200:
            info = response.json()
            print(f"\n📚 API Information:")
            print(f"   Name: {info.get('name')}")
            print(f"   Version: {info.get('version')}")
            print(f"   Endpoints: {len(info.get('endpoints', []))}")
            return info
        else:
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def main():
    """Main function"""
    print("\n" + "="*70)
    print("🏀 GradatumAI Video Analysis Test")
    print("="*70 + "\n")
    
    # Check API health
    if not check_api_health():
        print("\n⚠️  API Server is not responding!")
        print("   Please start it with: python api_server.py")
        return
    
    # Get API info
    get_api_info()
    
    # Analyze video
    job_id = analyze_video(VIDEO_PATH)
    
    if job_id:
        print(f"\n✅ Video analysis started successfully!")
        print(f"   Job ID: {job_id}")
        
        # Wait and check status
        print("\n⏳ Checking analysis status...")
        for i in range(5):
            time.sleep(2)
            status = get_analysis_status(job_id)
            if status and status.get('results_available'):
                print(f"\n✅ Analysis complete!")
                break
    else:
        print("\n❌ Could not start video analysis")
        print("   Try running 'python api_server.py' first")

if __name__ == '__main__':
    main()
