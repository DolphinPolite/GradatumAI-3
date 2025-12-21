#!/usr/bin/env python3
"""
Check video analysis results from API
"""

import requests
import json
from pathlib import Path

API_BASE_URL = "http://localhost:5000"

def get_results():
    """Get analysis results"""
    try:
        print("\n📊 Fetching analysis results...\n")
        
        response = requests.get(f"{API_BASE_URL}/api/results", timeout=5)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}\n")
        
        if response.status_code == 200:
            results = response.json()
            print("✅ Results found!\n")
            print(json.dumps(results, indent=2, ensure_ascii=False))
            return results
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def get_stats():
    """Get summary statistics"""
    try:
        print("\n📈 Fetching statistics...\n")
        
        response = requests.get(f"{API_BASE_URL}/api/stats/summary", timeout=5)
        
        if response.status_code == 200:
            stats = response.json()
            print("✅ Statistics found!\n")
            print(json.dumps(stats, indent=2, ensure_ascii=False))
            return stats
        else:
            print(f"❌ Error: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def check_output_dir():
    """Check if output directory has files"""
    print("\n🔍 Checking output directories...\n")
    
    output_dirs = [
        "api_results",
        "results",
        "visualizations"
    ]
    
    for dir_name in output_dirs:
        dir_path = Path(dir_name)
        if dir_path.exists():
            files = list(dir_path.glob("*"))
            print(f"  {dir_name}/: {len(files)} files")
            if files:
                for f in files[:5]:  # Show first 5
                    print(f"    - {f.name}")
        else:
            print(f"  {dir_name}/: (not found)")

def main():
    print("="*70)
    print("🏀 GradatumAI - Check Analysis Results")
    print("="*70)
    
    # Check API
    try:
        response = requests.get(f"{API_BASE_URL}/api/health", timeout=2)
        if response.status_code == 200:
            print("✅ API Server is running\n")
        else:
            print("⚠️  API Server is not responding properly\n")
    except:
        print("❌ Cannot connect to API Server\n")
        return
    
    # Check output directories
    check_output_dir()
    
    # Get results
    results = get_results()
    
    # Get stats
    stats = get_stats()
    
    print("\n" + "="*70)
    if results or stats:
        print("✅ Data available!")
    else:
        print("⚠️  No analysis results found yet")
    print("="*70)

if __name__ == '__main__':
    main()
