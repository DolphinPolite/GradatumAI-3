#!/usr/bin/env python3
"""
🏀 GradatumAI - Quick Start Guide

This script helps you get started with GradatumAI in less than 5 minutes.
Run this to verify your installation and start the system.

Usage:
    python quickstart.py
"""

import subprocess
import sys
import os
from pathlib import Path


class QuickStart:
    """Interactive quick start guide"""
    
    def __init__(self):
        self.root = Path(__file__).parent
        
    def print_header(self):
        """Print welcome header"""
        print("\n" + "="*70)
        print("🏀 GradatumAI Basketball Tracking System - Quick Start")
        print("="*70)
        print("\nWelcome! This guide will help you get started in 5 minutes.\n")
    
    def check_python(self):
        """Check Python version"""
        print("✓ Checking Python installation...")
        version = sys.version_info
        if version.major == 3 and version.minor >= 8:
            print(f"  ✅ Python {version.major}.{version.minor} found\n")
            return True
        else:
            print(f"  ❌ Python 3.8+ required (found {version.major}.{version.minor})\n")
            return False
    
    def check_files(self):
        """Check critical files"""
        print("✓ Checking project files...")
        critical_files = [
            'config/main_config.yaml',
            'api_server.py',
            'requirements.txt',
            'Dockerfile',
        ]
        
        all_exist = True
        for file in critical_files:
            if (self.root / file).exists():
                print(f"  ✅ {file}")
            else:
                print(f"  ❌ {file} (missing)")
                all_exist = False
        print()
        return all_exist
    
    def show_deployment_options(self):
        """Show deployment options"""
        print("="*70)
        print("📦 DEPLOYMENT OPTIONS")
        print("="*70 + "\n")
        
        options = [
            ("1", "Docker (Recommended for Production)",
             "docker-compose up -d",
             "✅ All services + API + Dashboard"),
            ("2", "Python (Development)",
             "python api_server.py",
             "✅ Simple local development"),
            ("3", "Complete Example",
             "python integration_example.py",
             "✅ Full analysis pipeline demo"),
            ("4", "Verify Installation",
             "python system_status.py",
             "✅ Check all components"),
        ]
        
        for num, desc, cmd, info in options:
            print(f"Option {num}: {desc}")
            print(f"  Command: {cmd}")
            print(f"  {info}\n")
        
        return input("Choose option (1-4): ").strip()
    
    def run_command(self, cmd):
        """Run a shell command"""
        try:
            print(f"\n📝 Running: {cmd}\n")
            subprocess.run(cmd, shell=True, check=False)
            return True
        except Exception as e:
            print(f"❌ Error running command: {e}\n")
            return False
    
    def show_next_steps(self):
        """Show what to do next"""
        print("\n" + "="*70)
        print("📚 NEXT STEPS")
        print("="*70 + "\n")
        
        steps = [
            ("1", "Read Documentation", "See INDEX.md for navigation guide"),
            ("2", "Test API", "curl http://localhost:5000/api/health"),
            ("3", "Access Dashboard", "http://localhost/ (Docker) or dashboard/index.html"),
            ("4", "Explore Modules", "Check Modules/ directory for analysis code"),
            ("5", "Process Video", "Put video in resources/ and run analysis"),
        ]
        
        for num, title, desc in steps:
            print(f"Step {num}: {title}")
            print(f"  → {desc}\n")
    
    def show_documentation(self):
        """Show documentation files"""
        print("\n" + "="*70)
        print("📖 DOCUMENTATION FILES")
        print("="*70 + "\n")
        
        docs = [
            ("INDEX.md", "📍 Navigation guide (START HERE)"),
            ("README.md", "📘 Complete project overview"),
            ("QUICKSTART.md", "⚡ 5-minute setup guide"),
            ("DEPLOYMENT_GUIDE.md", "🚀 Production deployment guide"),
            ("MODULES_COMPLETE.md", "🏗️  Architecture & modules"),
            ("api_server.py", "🔌 REST API server code"),
            ("integration_example.py", "💻 Complete working example"),
        ]
        
        for filename, description in docs:
            path = self.root / filename
            if path.exists():
                print(f"✅ {filename:<30} {description}")
            else:
                print(f"❌ {filename:<30} {description} (NOT FOUND)")
        print()
    
    def show_api_endpoints(self):
        """Show available API endpoints"""
        print("\n" + "="*70)
        print("🔌 API ENDPOINTS (After Starting Server)")
        print("="*70 + "\n")
        
        print("http://localhost:5000/api/\n")
        
        endpoints = [
            ("health", "Health check", "GET"),
            ("status", "Server status", "GET"),
            ("stats/summary", "Summary statistics", "GET"),
            ("stats/events", "Event statistics", "GET"),
            ("stats/shots", "Shot statistics", "GET"),
            ("export/csv", "Export as CSV", "GET"),
            ("export/json", "Export as JSON", "GET"),
            ("info", "Full API documentation", "GET"),
        ]
        
        for endpoint, desc, method in endpoints:
            print(f"  {method:4} /{endpoint:<25} {desc}")
        print()
    
    def run(self):
        """Run the quick start"""
        self.print_header()
        
        # Check Python
        if not self.check_python():
            print("❌ Python requirement not met. Please install Python 3.8 or higher.\n")
            return 1
        
        # Check files
        if not self.check_files():
            print("⚠️  Some files are missing. Make sure you're in the project directory.\n")
            return 1
        
        # Show documentation
        self.show_documentation()
        
        # Show API endpoints
        self.show_api_endpoints()
        
        # Show options
        choice = self.show_deployment_options()
        
        # Run selected option
        commands = {
            "1": "docker-compose up -d",
            "2": "python api_server.py",
            "3": "python integration_example.py",
            "4": "python system_status.py",
        }
        
        if choice in commands:
            self.run_command(commands[choice])
            self.show_next_steps()
            print("\n" + "="*70)
            print("✨ QUICK START COMPLETE ✨")
            print("="*70)
            
            if choice == "1":
                print("\n🎉 Docker services started!")
                print("   API: http://localhost:5000/api/health")
                print("   Dashboard: http://localhost/")
            elif choice == "2":
                print("\n🎉 API server started!")
                print("   Test: curl http://localhost:5000/api/health")
                print("   Dashboard: Open dashboard/index.html in browser")
            elif choice == "3":
                print("\n🎉 Example analysis complete!")
                print("   Check results/ and visualizations/ directories")
            elif choice == "4":
                print("\n✅ System verification complete!")
                print("   Follow the recommended next steps above")
            
            return 0
        else:
            print("❌ Invalid option. Please choose 1-4.\n")
            return 1


def main():
    """Main entry point"""
    qs = QuickStart()
    exit_code = qs.run()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
