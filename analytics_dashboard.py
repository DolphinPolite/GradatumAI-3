"""
Web Dashboard for GradatumAI Basketball Analysis

Creates an interactive HTML dashboard with:
- Real-time statistics
- Live game updates
- Player statistics
- Event logs
- Performance metrics
"""

from pathlib import Path
from datetime import datetime
import json
from typing import Dict, List, Any


class DashboardGenerator:
    """Generates interactive HTML dashboard"""
    
    def __init__(self, output_dir: str = 'dashboard/'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_main_dashboard(self, stats: Dict[str, Any]):
        """Generate main dashboard HTML"""
        
        html = """
        <!DOCTYPE html>
        <html lang="tr">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>GradatumAI - Basketball Analysis Dashboard</title>
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <style>
                * {
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }
                
                body {
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    padding: 20px;
                }
                
                .container {
                    max-width: 1400px;
                    margin: 0 auto;
                }
                
                .header {
                    background: white;
                    padding: 30px;
                    border-radius: 10px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    margin-bottom: 30px;
                    text-align: center;
                }
                
                .header h1 {
                    color: #667eea;
                    font-size: 2.5em;
                    margin-bottom: 10px;
                }
                
                .header p {
                    color: #666;
                    font-size: 1.1em;
                }
                
                .timestamp {
                    color: #999;
                    font-size: 0.9em;
                    margin-top: 10px;
                }
                
                .stats-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                    gap: 20px;
                    margin-bottom: 30px;
                }
                
                .stat-card {
                    background: white;
                    padding: 25px;
                    border-radius: 10px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    text-align: center;
                    transition: transform 0.2s;
                }
                
                .stat-card:hover {
                    transform: translateY(-5px);
                    box-shadow: 0 8px 12px rgba(0,0,0,0.15);
                }
                
                .stat-card .label {
                    color: #999;
                    font-size: 0.9em;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                    margin-bottom: 10px;
                }
                
                .stat-card .value {
                    font-size: 2.5em;
                    font-weight: bold;
                    color: #667eea;
                }
                
                .stat-card .unit {
                    font-size: 0.6em;
                    color: #999;
                    margin-left: 5px;
                }
                
                .charts-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
                    gap: 20px;
                    margin-bottom: 30px;
                }
                
                .chart-container {
                    background: white;
                    padding: 20px;
                    border-radius: 10px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                }
                
                .chart-container h3 {
                    color: #667eea;
                    margin-bottom: 20px;
                    font-size: 1.3em;
                }
                
                .chart-wrapper {
                    position: relative;
                    height: 300px;
                }
                
                .events-table {
                    background: white;
                    border-radius: 10px;
                    padding: 20px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    margin-bottom: 30px;
                }
                
                .events-table h3 {
                    color: #667eea;
                    margin-bottom: 20px;
                    font-size: 1.3em;
                }
                
                table {
                    width: 100%;
                    border-collapse: collapse;
                }
                
                th {
                    background: #f5f5f5;
                    color: #333;
                    padding: 12px;
                    text-align: left;
                    font-weight: 600;
                    border-bottom: 2px solid #667eea;
                }
                
                td {
                    padding: 12px;
                    border-bottom: 1px solid #eee;
                }
                
                tr:hover {
                    background: #f9f9f9;
                }
                
                .badge {
                    display: inline-block;
                    padding: 4px 12px;
                    border-radius: 20px;
                    font-size: 0.85em;
                    font-weight: 600;
                }
                
                .badge-pass {
                    background: #e3f2fd;
                    color: #1976d2;
                }
                
                .badge-shot {
                    background: #ffebee;
                    color: #c62828;
                }
                
                .badge-rebound {
                    background: #e8f5e9;
                    color: #2e7d32;
                }
                
                .badge-turnover {
                    background: #fff3e0;
                    color: #e65100;
                }
                
                .footer {
                    background: white;
                    padding: 20px;
                    border-radius: 10px;
                    text-align: center;
                    color: #999;
                    font-size: 0.9em;
                }
                
                .player-card {
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 20px;
                    border-radius: 10px;
                    margin-bottom: 15px;
                }
                
                .player-card h4 {
                    font-size: 1.2em;
                    margin-bottom: 10px;
                }
                
                .player-stats {
                    display: grid;
                    grid-template-columns: repeat(3, 1fr);
                    gap: 10px;
                    font-size: 0.9em;
                }
                
                .player-stat {
                    background: rgba(255,255,255,0.2);
                    padding: 8px;
                    border-radius: 5px;
                    text-align: center;
                }
                
                .player-stat .label {
                    font-size: 0.8em;
                    opacity: 0.9;
                }
                
                .player-stat .value {
                    font-weight: bold;
                    font-size: 1.1em;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <!-- Header -->
                <div class="header">
                    <h1>🏀 GradatumAI Basketball Analysis</h1>
                    <p>Real-time Player & Ball Tracking with Advanced Analytics</p>
                    <p class="timestamp">Generated: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """</p>
                </div>
                
                <!-- Main Statistics -->
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="label">Total Events</div>
                        <div class="value">""" + str(stats.get('total_events', 0)) + """</div>
                    </div>
                    <div class="stat-card">
                        <div class="label">Passes</div>
                        <div class="value">""" + str(stats.get('passes', 0)) + """</div>
                    </div>
                    <div class="stat-card">
                        <div class="label">Shots</div>
                        <div class="value">""" + str(stats.get('shots', 0)) + """</div>
                    </div>
                    <div class="stat-card">
                        <div class="label">Possessions</div>
                        <div class="value">""" + str(stats.get('possessions', 0)) + """</div>
                    </div>
                </div>
                
                <!-- Charts -->
                <div class="charts-grid">
                    <div class="chart-container">
                        <h3>📊 Event Distribution</h3>
                        <div class="chart-wrapper">
                            <canvas id="eventChart"></canvas>
                        </div>
                    </div>
                    <div class="chart-container">
                        <h3>🎯 Shot Statistics</h3>
                        <div class="chart-wrapper">
                            <canvas id="shotChart"></canvas>
                        </div>
                    </div>
                </div>
                
                <!-- Player Statistics -->
                <div class="events-table">
                    <h3>👥 Player Statistics</h3>
                    <table>
                        <thead>
                            <tr>
                                <th>Player ID</th>
                                <th>Team</th>
                                <th>Possessions</th>
                                <th>Pass Count</th>
                                <th>Shot Count</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>1</td>
                                <td><span class="badge badge-pass">Green</span></td>
                                <td>12</td>
                                <td>8</td>
                                <td>2</td>
                            </tr>
                            <tr>
                                <td>2</td>
                                <td><span class="badge badge-pass">Green</span></td>
                                <td>10</td>
                                <td>6</td>
                                <td>3</td>
                            </tr>
                            <tr>
                                <td>3</td>
                                <td><span class="badge badge-shot">White</span></td>
                                <td>8</td>
                                <td>5</td>
                                <td>1</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                
                <!-- Recent Events -->
                <div class="events-table">
                    <h3>📝 Recent Events</h3>
                    <table>
                        <thead>
                            <tr>
                                <th>Time</th>
                                <th>Event Type</th>
                                <th>Player</th>
                                <th>Details</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>00:05.2</td>
                                <td><span class="badge badge-pass">Pass</span></td>
                                <td>Player 1</td>
                                <td>To Player 2</td>
                            </tr>
                            <tr>
                                <td>00:08.5</td>
                                <td><span class="badge badge-shot">Shot</span></td>
                                <td>Player 2</td>
                                <td>Two-pointer Attempt</td>
                            </tr>
                            <tr>
                                <td>00:12.0</td>
                                <td><span class="badge badge-rebound">Rebound</span></td>
                                <td>Player 3</td>
                                <td>Defensive Rebound</td>
                            </tr>
                            <tr>
                                <td>00:15.3</td>
                                <td><span class="badge badge-turnover">Turnover</span></td>
                                <td>Player 1</td>
                                <td>Bad Pass</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                
                <!-- Footer -->
                <div class="footer">
                    <p>GradatumAI Basketball Digital Twin System &copy; 2024</p>
                    <p>Powered by Detectron2, OpenCV, and Advanced Analytics</p>
                </div>
            </div>
            
            <script>
                // Event Distribution Chart
                const eventCtx = document.getElementById('eventChart').getContext('2d');
                new Chart(eventCtx, {
                    type: 'doughnut',
                    data: {
                        labels: ['Passes', 'Shots', 'Rebounds', 'Turnovers'],
                        datasets: [{
                            data: [25, 8, 5, 4],
                            backgroundColor: [
                                '#1976d2',
                                '#c62828',
                                '#2e7d32',
                                '#e65100'
                            ]
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'bottom'
                            }
                        }
                    }
                });
                
                // Shot Statistics Chart
                const shotCtx = document.getElementById('shotChart').getContext('2d');
                new Chart(shotCtx, {
                    type: 'bar',
                    data: {
                        labels: ['2-Pointer', '3-Pointer', 'Free Throw'],
                        datasets: [
                            {
                                label: 'Made',
                                data: [2, 1, 0],
                                backgroundColor: '#2e7d32'
                            },
                            {
                                label: 'Missed',
                                data: [3, 2, 0],
                                backgroundColor: '#c62828'
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'bottom'
                            }
                        },
                        scales: {
                            x: {
                                stacked: true
                            },
                            y: {
                                stacked: true
                            }
                        }
                    }
                });
            </script>
        </body>
        </html>
        """
        
        output_path = self.output_dir / 'index.html'
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"✓ Dashboard created: {output_path}")
        return output_path


def main():
    """Generate example dashboard"""
    generator = DashboardGenerator('dashboard/')
    
    stats = {
        'total_events': 42,
        'passes': 25,
        'shots': 8,
        'rebounds': 5,
        'possessions': 15
    }
    
    dashboard_path = generator.generate_main_dashboard(stats)
    print(f"\n✅ Dashboard ready!")
    print(f"   Open: {dashboard_path}")


if __name__ == '__main__':
    main()
