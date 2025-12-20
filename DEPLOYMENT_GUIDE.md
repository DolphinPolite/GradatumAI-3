# 🚀 GradatumAI Production Deployment Guide

Complete guide for deploying GradatumAI basketball tracking system in production environments.

## Table of Contents

1. [Docker Deployment](#docker-deployment)
2. [API Server Setup](#api-server-setup)
3. [Dashboard Access](#dashboard-access)
4. [Production Checklist](#production-checklist)
5. [Troubleshooting](#troubleshooting)
6. [Performance Optimization](#performance-optimization)

---

## Docker Deployment

### Prerequisites

- Docker 20.10+ installed
- Docker Compose 1.29+ installed
- 4GB+ RAM available
- 10GB+ disk space

### Quick Start

```bash
# Clone or navigate to project
cd GradatumAI-3-main

# Build and start services
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f api
```

### Build Custom Image

```bash
# Build image with custom tag
docker build -t gradatum-ai:latest .

# Run container
docker run -d \
  --name gradatum-api \
  -p 5000:5000 \
  -v $(pwd)/resources:/app/resources \
  -v $(pwd)/results:/app/results \
  gradatum-ai:latest

# Check logs
docker logs -f gradatum-api
```

### Multi-Service Deployment

```bash
# Start all services (API + Redis + Nginx)
docker-compose up -d

# Scale API service (if using Kubernetes)
docker-compose up -d --scale api=3

# Stop all services
docker-compose down

# Clean up volumes
docker-compose down -v
```

---

## API Server Setup

### Using Flask Development Server

```bash
# Install dependencies
pip install -r requirements.txt

# Configure settings (optional)
export FLASK_ENV=production
export FLASK_DEBUG=0

# Run server
python api_server.py
```

### Using Production WSGI Server (Gunicorn)

```bash
# Install Gunicorn
pip install gunicorn

# Run with Gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 api_server:app

# Run with worker threads
gunicorn -w 4 -k gthread --threads 2 -b 0.0.0.0:5000 api_server:app

# Run with auto-reload on code changes
gunicorn --reload -b 0.0.0.0:5000 api_server:app
```

### Using Systemd Service (Linux)

Create `/etc/systemd/system/gradatum-api.service`:

```ini
[Unit]
Description=GradatumAI Basketball Analysis API
After=network.target

[Service]
Type=notify
User=www-data
WorkingDirectory=/home/user/GradatumAI-3-main
Environment="PATH=/home/user/GradatumAI-3-main/venv/bin"
ExecStart=/home/user/GradatumAI-3-main/venv/bin/gunicorn \
    -w 4 -b 127.0.0.1:5000 api_server:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable gradatum-api
sudo systemctl start gradatum-api
sudo systemctl status gradatum-api
```

---

## Dashboard Access

### Local Access

```
API Server:      http://localhost:5000
Health Check:    http://localhost:5000/api/health
API Info:        http://localhost:5000/api/info
Dashboard:       Open dashboard/index.html in browser
```

### Remote Access (via Nginx Proxy)

```
API Endpoint:    http://<server-ip>/api/
Dashboard:       http://<server-ip>/
```

### API Endpoints Reference

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health` | GET | Health check |
| `/api/status` | GET | Server status |
| `/api/analyze` | POST | Start video analysis |
| `/api/results` | GET | Get analysis results |
| `/api/stats/events` | GET | Event statistics |
| `/api/stats/shots` | GET | Shot statistics |
| `/api/stats/possession` | GET | Possession statistics |
| `/api/stats/distance` | GET | Distance analytics |
| `/api/stats/summary` | GET | Summary statistics |
| `/api/export/csv` | GET | Export as CSV |
| `/api/export/json` | GET | Export as JSON |
| `/api/export/stats` | GET | Export statistics |
| `/api/visualizations/generate` | POST | Generate visualizations |
| `/api/info` | GET | API documentation |

### Example API Calls

```bash
# Health check
curl http://localhost:5000/api/health

# Get server status
curl http://localhost:5000/api/status

# Get event statistics
curl http://localhost:5000/api/stats/events

# Get summary statistics
curl http://localhost:5000/api/stats/summary

# Export as CSV
curl http://localhost:5000/api/export/csv -o analysis.csv

# Start analysis (requires video file)
curl -X POST http://localhost:5000/api/analyze \
  -F "video=@path/to/video.mp4"

# Generate visualizations
curl -X POST http://localhost:5000/api/visualizations/generate \
  -H "Content-Type: application/json" \
  -d '{"format": "html"}'
```

---

## Production Checklist

### Security

- [ ] Use HTTPS/SSL certificates
- [ ] Set up firewall rules (only open port 80, 443)
- [ ] Enable authentication for API endpoints
- [ ] Use API keys for external access
- [ ] Keep dependencies updated
- [ ] Run security scanning on Docker image
- [ ] Use environment variables for sensitive data
- [ ] Implement rate limiting

### Performance

- [ ] Configure appropriate worker count (2-4 per CPU core)
- [ ] Enable caching (Redis)
- [ ] Use CDN for static assets
- [ ] Implement database optimization
- [ ] Monitor CPU and memory usage
- [ ] Set up log rotation
- [ ] Enable compression for API responses
- [ ] Use connection pooling

### Monitoring & Logging

- [ ] Set up centralized logging (ELK stack)
- [ ] Configure health check monitoring
- [ ] Set up alerting for critical errors
- [ ] Monitor API response times
- [ ] Track resource usage (CPU, RAM, disk)
- [ ] Implement distributed tracing
- [ ] Set up uptime monitoring

### Backup & Recovery

- [ ] Automated backup of analysis results
- [ ] Database backup strategy
- [ ] Disaster recovery plan
- [ ] Regular restore testing
- [ ] Document recovery procedures

### Deployment

- [ ] Use version control for all code
- [ ] Implement CI/CD pipeline
- [ ] Test all changes before deployment
- [ ] Use blue-green deployments
- [ ] Maintain rollback capability
- [ ] Document deployment procedures
- [ ] Create runbooks for common issues

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker logs gradatum-api

# Inspect container
docker inspect gradatum-api

# Run with interactive terminal
docker run -it --entrypoint /bin/bash gradatum-ai:latest

# Check resource limits
docker stats gradatum-api
```

### API Connection Issues

```bash
# Test connectivity
curl -v http://localhost:5000/api/health

# Check port is open
netstat -tuln | grep 5000

# Check container network
docker network inspect gradatum-network

# Restart service
docker-compose restart api
```

### Out of Memory Issues

```bash
# Check memory usage
docker stats

# Limit memory in docker-compose.yml
services:
  api:
    mem_limit: 2g
    memswap_limit: 2g

# Monitor with interval
docker stats --no-stream gradatum-api
```

### Performance Issues

```bash
# Profile Python application
python -m cProfile -o profile.stats api_server.py

# Analyze profile
python -c "import pstats; p = pstats.Stats('profile.stats'); p.sort_stats('cumulative').print_stats(10)"

# Monitor with top
top -p $(docker inspect -f '{{.State.Pid}}' gradatum-api)

# Check file descriptor limits
cat /proc/$(docker inspect -f '{{.State.Pid}}' gradatum-api)/limits
```

### Video Processing Hangs

```bash
# Increase timeout
API_TIMEOUT=600 docker-compose up -d

# Check processing status
curl http://localhost:5000/api/status

# Kill stuck process (if needed)
docker exec gradatum-api pkill -f "python api_server.py"

# Clear processing queue
curl -X POST http://localhost:5000/api/reset
```

---

## Performance Optimization

### Python/Flask Optimization

```python
# Use compiled modules
pip install uwsgi

# Enable compression
from flask_compress import Compress
Compress(app)

# Cache responses
from flask_caching import Cache
cache = Cache(app, config={'CACHE_TYPE': 'redis'})

# Use async tasks
from celery import Celery
celery = Celery(app.name, broker='redis://localhost:6379')
```

### Docker Optimization

```dockerfile
# Use slim base image
FROM python:3.9-slim

# Multi-stage build to reduce image size
FROM python:3.9-slim as builder
# ... build dependencies ...

FROM python:3.9-slim
# ... copy from builder ...
```

### System Tuning

```bash
# Increase file descriptors
ulimit -n 65535

# Network optimization
sysctl -w net.core.somaxconn=65535
sysctl -w net.ipv4.tcp_max_syn_backlog=65535

# Disable unnecessary services
systemctl disable apache2
systemctl disable bluetooth
```

### Resource Monitoring

```bash
# Monitor in real-time
docker stats --no-stream

# Set up Prometheus monitoring
docker run -d -p 9090:9090 prom/prometheus

# Use Grafana for visualization
docker run -d -p 3000:3000 grafana/grafana
```

---

## Maintenance

### Regular Maintenance Tasks

```bash
# Update dependencies
pip install --upgrade -r requirements.txt

# Clean up Docker resources
docker system prune -a

# Rotate logs
logrotate /etc/logrotate.d/gradatum-api

# Update Docker image
docker pull python:3.9-slim
docker-compose build --no-cache
docker-compose up -d
```

### Backup Procedures

```bash
# Backup analysis results
tar -czf backup-$(date +%Y%m%d).tar.gz results/ visualizations/

# Export database
docker exec gradatum-redis redis-cli BGSAVE

# Backup configuration
cp -r config/ config-backup-$(date +%Y%m%d)/
```

### Log Management

```bash
# View recent logs
docker logs -n 100 gradatum-api

# Follow logs in real-time
docker logs -f gradatum-api

# Export logs
docker logs gradatum-api > api.log 2>&1

# Configure log rotation in docker-compose.yml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

---

## Support & Documentation

- **GitHub Issues**: Report bugs and request features
- **Documentation**: See README.md and module docstrings
- **API Documentation**: http://localhost:5000/api/info
- **Example Scripts**: See `integration_example.py` for usage patterns

## Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [OpenCV Documentation](https://docs.opencv.org/)
- [Detectron2 GitHub](https://github.com/facebookresearch/detectron2)
