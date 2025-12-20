@echo off
REM GradatumAI Deployment Commands for Windows
REM Copy and paste commands in Command Prompt or PowerShell

REM =============================================================================
REM OPTION 1: DOCKER DEPLOYMENT (RECOMMENDED)
REM =============================================================================

echo.
echo ===============================================================================
echo OPTION 1: Docker Deployment (Recommended for Production)
echo ===============================================================================
echo.
echo Start all services:
echo   docker-compose up -d
echo.
echo Check status:
echo   docker-compose ps
echo.
echo View logs:
echo   docker-compose logs -f api
echo.
echo Stop services:
echo   docker-compose down
echo.
echo Access points:
echo   API: http://localhost:5000
echo   Health: http://localhost:5000/api/health
echo   Dashboard: http://localhost/
echo.

REM =============================================================================
REM OPTION 2: PYTHON DEVELOPMENT DEPLOYMENT
REM =============================================================================

echo ===============================================================================
echo OPTION 2: Python Development Deployment
echo ===============================================================================
echo.
echo Create virtual environment:
echo   python -m venv venv
echo.
echo Activate environment (Windows Command Prompt):
echo   venv\Scripts\activate.bat
echo.
echo Activate environment (Windows PowerShell):
echo   venv\Scripts\Activate.ps1
echo.
echo Install dependencies:
echo   pip install -r requirements.txt
echo.
echo Start API server:
echo   python api_server.py
echo.
echo In another terminal, generate dashboard:
echo   python analytics_dashboard.py
echo.
echo Access points:
echo   API: http://localhost:5000
echo   API Info: http://localhost:5000/api/info
echo   Dashboard: Open dashboard/index.html in browser
echo.

REM =============================================================================
REM OPTION 3: VERIFICATION
REM =============================================================================

echo ===============================================================================
echo OPTION 3: Verify Installation
echo ===============================================================================
echo.
echo Check system status:
echo   python system_status.py
echo.
echo Test API connectivity:
echo   curl http://localhost:5000/api/health
echo.
echo Run integration example:
echo   python integration_example.py
echo.
echo Run tests (if pytest installed):
echo   pytest tests/test_modules_integration.py -v
echo.

REM =============================================================================
REM API TESTING COMMANDS
REM =============================================================================

echo ===============================================================================
echo API Testing Commands
echo ===============================================================================
echo.
echo Health check:
echo   curl http://localhost:5000/api/health
echo.
echo Get server status:
echo   curl http://localhost:5000/api/status
echo.
echo Get event statistics:
echo   curl http://localhost:5000/api/stats/events
echo.
echo Get shot statistics:
echo   curl http://localhost:5000/api/stats/shots
echo.
echo Get summary statistics:
echo   curl http://localhost:5000/api/stats/summary
echo.
echo Export as CSV:
echo   curl http://localhost:5000/api/export/csv -o analysis.csv
echo.
echo Export as JSON:
echo   curl http://localhost:5000/api/export/json -o analysis.json
echo.
echo Get API documentation:
echo   curl http://localhost:5000/api/info
echo.

REM =============================================================================
REM DOCKER MANAGEMENT (if using Docker)
REM =============================================================================

echo ===============================================================================
echo Docker Management Commands
echo ===============================================================================
echo.
echo Build custom image:
echo   docker build -t gradatum-ai:latest .
echo.
echo Run container manually:
echo   docker run -d --name gradatum-api -p 5000:5000 ^
echo     -v %%cd%%\resources:/app/resources gradatum-ai:latest
echo.
echo View logs:
echo   docker logs -f gradatum-api
echo.
echo Stop and remove:
echo   docker stop gradatum-api
echo   docker rm gradatum-api
echo.
echo Check resource usage:
echo   docker stats gradatum-api
echo.
echo Clean up all:
echo   docker system prune -a
echo.

REM =============================================================================
REM QUICK SETUP SCRIPT
REM =============================================================================

echo ===============================================================================
echo Quick Setup (Copy and Run Line by Line)
echo ===============================================================================
echo.
echo Step 1: Install Python dependencies
echo   pip install -r requirements.txt
echo.
echo Step 2: Verify installation
echo   python system_status.py
echo.
echo Step 3: Choose ONE of these:
echo.
echo   Option A - Run as Docker (needs Docker installed):
echo     docker-compose up -d
echo.
echo   Option B - Run as Python (development):
echo     python api_server.py
echo.
echo   Option C - Run complete example:
echo     python integration_example.py
echo.
echo Step 4: Test the API
echo   curl http://localhost:5000/api/health
echo.
echo Step 5: Access the dashboard
echo   Open: http://localhost/ (if using Docker)
echo   Or: Open dashboard/index.html in browser
echo.

REM =============================================================================
REM FILE PATHS AND IMPORTANT FILES
REM =============================================================================

echo ===============================================================================
echo Important Files and Documentation
echo ===============================================================================
echo.
echo Configuration:
echo   config/main_config.yaml - All system parameters
echo.
echo Documentation:
echo   README.md - Complete overview
echo   QUICKSTART.md - Quick start guide
echo   DEPLOYMENT_GUIDE.md - Production deployment guide
echo   PRODUCTION_COMPLETE.md - System status
echo   INDEX.md - Navigation guide
echo.
echo Code:
echo   api_server.py - REST API server
echo   analytics_dashboard.py - Web dashboard
echo   visualization_suite.py - Chart generation
echo   integration_example.py - Complete working example
echo   system_status.py - System verification
echo.
echo Analysis Modules (in Modules/ directory):
echo   BallControl - Possession analysis
echo   DriblingDetector - Dribbling detection
echo   EventRecognition - Game event recognition
echo   ShotAttemp - Shot analysis
echo   SequenceParser - Data export
echo   PlayerDistance - Distance analytics
echo.

REM =============================================================================
REM TROUBLESHOOTING
REM =============================================================================

echo ===============================================================================
echo Troubleshooting
echo ===============================================================================
echo.
echo If Docker won't start:
echo   1. Check Docker is installed: docker --version
echo   2. Check Docker daemon is running
echo   3. View logs: docker-compose logs api
echo.
echo If Python dependencies fail:
echo   1. Use a virtual environment: python -m venv venv
echo   2. Activate it: venv\Scripts\activate.bat
echo   3. Reinstall: pip install -r requirements.txt
echo.
echo If API won't connect:
echo   1. Check it's running: curl http://localhost:5000/api/health
echo   2. Check port 5000 is available
echo   3. View logs: python api_server.py
echo.
echo If tests fail:
echo   1. Install pytest: pip install pytest
echo   2. Run tests: pytest tests/test_modules_integration.py -v
echo.

REM =============================================================================
REM NEXT STEPS
REM =============================================================================

echo ===============================================================================
echo Next Steps
echo ===============================================================================
echo.
echo 1. Read documentation:
echo    - Start with: INDEX.md (navigation guide)
echo    - Then: README.md (project overview)
echo    - Finally: QUICKSTART.md (5-minute setup)
echo.
echo 2. Choose deployment method and run commands from above
echo.
echo 3. Verify installation:
echo    python system_status.py
echo.
echo 4. Access the system:
echo    API: http://localhost:5000/api/health
echo    Dashboard: http://localhost/ (Docker) or dashboard/index.html
echo.
echo 5. Test the API:
echo    curl http://localhost:5000/api/stats/summary
echo.
echo ===============================================================================
echo Setup Complete! System is ready for use.
echo ===============================================================================
echo.

pause
