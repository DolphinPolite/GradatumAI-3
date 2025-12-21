#!/bin/bash
# GradatumAI Deployment Commands
# Copy and paste commands below for quick deployment

# =============================================================================
# OPTION 1: DOCKER DEPLOYMENT (RECOMMENDED FOR PRODUCTION)
# =============================================================================

echo "=== Docker Deployment ==="
echo "Start all services (API + Redis + Nginx):"
echo "  docker-compose up -d"
echo ""
echo "Check status:"
echo "  docker-compose ps"
echo ""
echo "View logs:"
echo "  docker-compose logs -f api"
echo ""
echo "Stop services:"
echo "  docker-compose down"
echo ""
echo "Access points:"
echo "  API: http://localhost:5000"
echo "  Health: http://localhost:5000/api/health"
echo "  Dashboard: http://localhost/"
echo ""

# =============================================================================
# OPTION 2: PYTHON DEVELOPMENT DEPLOYMENT
# =============================================================================

echo "=== Python Development Deployment ==="
echo "Create virtual environment:"
echo "  python -m venv venv"
echo ""
echo "Activate environment:"
echo "  # On Linux/Mac:"
echo "  source venv/bin/activate"
echo "  # On Windows:"
echo "  venv\\Scripts\\activate"
echo ""
echo "Install dependencies:"
echo "  pip install -r requirements.txt"
echo ""
echo "Start API server:"
echo "  python api_server.py"
echo ""
echo "In another terminal, generate dashboard:"
echo "  python analytics_dashboard.py"
echo ""
echo "Access points:"
echo "  API: http://localhost:5000"
echo "  API Info: http://localhost:5000/api/info"
echo "  Dashboard: Open dashboard/index.html in browser"
echo ""

# =============================================================================
# OPTION 3: GUNICORN PRODUCTION SERVER
# =============================================================================

echo "=== Production WSGI Server (Gunicorn) ==="
echo "Install Gunicorn:"
echo "  pip install gunicorn"
echo ""
echo "Run with auto-reload:"
echo "  gunicorn --reload -b 0.0.0.0:5000 api_server:app"
echo ""
echo "Run with worker threads:"
echo "  gunicorn -w 4 -k gthread --threads 2 -b 0.0.0.0:5000 api_server:app"
echo ""
echo "Run with multiple workers (production):"
echo "  gunicorn -w 4 -b 0.0.0.0:5000 api_server:app"
echo ""

# =============================================================================
# OPTION 4: SYSTEMD SERVICE (LINUX PRODUCTION)
# =============================================================================

echo "=== Systemd Service Setup (Linux) ==="
echo "Create service file:"
echo "  sudo nano /etc/systemd/system/gradatum-api.service"
echo ""
echo "Paste this content:"
echo "---"
echo "[Unit]"
echo "Description=GradatumAI Basketball Analysis API"
echo "After=network.target"
echo ""
echo "[Service]"
echo "Type=notify"
echo "User=www-data"
echo "WorkingDirectory=/home/user/GradatumAI-3-main"
echo "Environment=\"PATH=/home/user/GradatumAI-3-main/venv/bin\""
echo "ExecStart=/home/user/GradatumAI-3-main/venv/bin/gunicorn \\"
echo "    -w 4 -b 127.0.0.1:5000 api_server:app"
echo "Restart=always"
echo "RestartSec=10"
echo ""
echo "[Install]"
echo "WantedBy=multi-user.target"
echo "---"
echo ""
echo "Enable and start:"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable gradatum-api"
echo "  sudo systemctl start gradatum-api"
echo "  sudo systemctl status gradatum-api"
echo ""
echo "View logs:"
echo "  sudo journalctl -u gradatum-api -f"
echo ""

# =============================================================================
# VERIFY INSTALLATION
# =============================================================================

echo "=== Verify Installation ==="
echo "Check system status:"
echo "  python system_status.py"
echo ""
echo "Test API connectivity:"
echo "  curl http://localhost:5000/api/health"
echo ""
echo "Run integration example:"
echo "  python integration_example.py"
echo ""
echo "Run tests:"
echo "  pytest tests/test_modules_integration.py -v"
echo ""

# =============================================================================
# API TESTING COMMANDS
# =============================================================================

echo "=== API Testing ==="
echo "Health check:"
echo "  curl http://localhost:5000/api/health"
echo ""
echo "Get server status:"
echo "  curl http://localhost:5000/api/status"
echo ""
echo "Get event statistics:"
echo "  curl http://localhost:5000/api/stats/events"
echo ""
echo "Get shot statistics:"
echo "  curl http://localhost:5000/api/stats/shots"
echo ""
echo "Get possession statistics:"
echo "  curl http://localhost:5000/api/stats/possession"
echo ""
echo "Get distance analytics:"
echo "  curl http://localhost:5000/api/stats/distance"
echo ""
echo "Get summary:"
echo "  curl http://localhost:5000/api/stats/summary"
echo ""
echo "Export as CSV:"
echo "  curl http://localhost:5000/api/export/csv -o analysis.csv"
echo ""
echo "Export as JSON:"
echo "  curl http://localhost:5000/api/export/json -o analysis.json"
echo ""
echo "Get API info:"
echo "  curl http://localhost:5000/api/info"
echo ""

# =============================================================================
# DOCKER MANAGEMENT COMMANDS
# =============================================================================

echo "=== Docker Management ==="
echo "Build custom image:"
echo "  docker build -t gradatum-ai:latest ."
echo ""
echo "Run container manually:"
echo "  docker run -d --name gradatum-api \\"
echo "    -p 5000:5000 \\"
echo "    -v \$(pwd)/resources:/app/resources \\"
echo "    gradatum-ai:latest"
echo ""
echo "View logs:"
echo "  docker logs -f gradatum-api"
echo ""
echo "Stop and remove:"
echo "  docker stop gradatum-api"
echo "  docker rm gradatum-api"
echo ""
echo "Check resource usage:"
echo "  docker stats gradatum-api"
echo ""
echo "Clean up all:"
echo "  docker system prune -a"
echo ""

# =============================================================================
# MAINTENANCE COMMANDS
# =============================================================================

echo "=== Maintenance ==="
echo "Update dependencies:"
echo "  pip install --upgrade -r requirements.txt"
echo ""
echo "Backup results:"
echo "  tar -czf backup-\$(date +%Y%m%d).tar.gz results/ visualizations/"
echo ""
echo "Clean cache:"
echo "  rm -rf __pycache__ Modules/**/__pycache__"
echo ""
echo "View configuration:"
echo "  cat config/main_config.yaml"
echo ""
echo "Edit configuration:"
echo "  nano config/main_config.yaml"
echo ""

# =============================================================================
# HELP & DOCUMENTATION
# =============================================================================

echo "=== Documentation Links ==="
echo "Quick start: See QUICKSTART.md"
echo "Full guide: See README.md"
echo "API docs: See DEPLOYMENT_GUIDE.md"
echo "Architecture: See MODULES_COMPLETE.md"
echo "Completion status: See PRODUCTION_COMPLETE.md"
echo "Navigation: See INDEX.md"
echo ""
echo "=== Support ==="
echo "Check system: python system_status.py"
echo "View API docs: curl http://localhost:5000/api/info"
echo "Run example: python integration_example.py"
echo ""

echo "✅ All commands ready for use!"
echo "Choose your deployment method and copy the commands above."
