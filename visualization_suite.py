"""
Comprehensive Visualization Suite for GradatumAI

Creates various visualizations:
- Player movement heatmaps
- Event timeline plots
- Distance analysis heatmaps
- Shot distribution maps
- Possession timeline
- Speed/acceleration graphs
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import seaborn as sns
from datetime import datetime


class BasketballVisualizer:
    """Creates basketball-specific visualizations"""
    
    def __init__(self, output_dir: str = 'visualizations/'):
        """Initialize visualizer"""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Court dimensions (meters)
        self.court_width = 28.0
        self.court_height = 15.0
        
        # Setup style
        plt.style.use('seaborn-v0_8-darkgrid')
        sns.set_palette("husl")
    
    def plot_court(self, ax=None) -> plt.Axes:
        """Draw basketball court on axes"""
        if ax is None:
            fig, ax = plt.subplots(figsize=(14, 10))
        
        # Court boundary
        ax.plot([0, self.court_width], [0, 0], 'k-', linewidth=2)
        ax.plot([0, self.court_width], [self.court_height, self.court_height], 'k-', linewidth=2)
        ax.plot([0, 0], [0, self.court_height], 'k-', linewidth=2)
        ax.plot([self.court_width, self.court_width], [0, self.court_height], 'k-', linewidth=2)
        
        # Center circle
        circle = patches.Circle((self.court_width/2, self.court_height/2), 
                               1.8, fill=False, edgecolor='k', linewidth=1)
        ax.add_patch(circle)
        
        # Free throw circles
        circle_left = patches.Circle((5.25, self.court_height/2), 1.8, 
                                    fill=False, edgecolor='k', linewidth=1)
        circle_right = patches.Circle((self.court_width - 5.25, self.court_height/2), 1.8, 
                                     fill=False, edgecolor='k', linewidth=1)
        ax.add_patch(circle_left)
        ax.add_patch(circle_right)
        
        # Hoop positions
        ax.plot([5.25], [self.court_height/2], 'ro', markersize=8)
        ax.plot([self.court_width - 5.25], [self.court_height/2], 'ro', markersize=8)
        
        ax.set_xlim(-1, self.court_width + 1)
        ax.set_ylim(-1, self.court_height + 1)
        ax.set_aspect('equal')
        ax.set_xlabel('Court Width (meters)')
        ax.set_ylabel('Court Height (meters)')
        
        return ax
    
    def plot_player_heatmap(self, 
                           player_id: int,
                           trajectory: List[Tuple[float, float]],
                           title: str = None):
        """
        Plot player movement heatmap
        
        Args:
            player_id: Player ID
            trajectory: List of (x, y) positions
            title: Plot title
        """
        fig, ax = plt.subplots(figsize=(14, 10))
        self.plot_court(ax)
        
        if trajectory:
            positions = np.array(trajectory)
            
            # Create 2D histogram
            h = ax.hist2d(positions[:, 0], positions[:, 1], 
                         bins=20, cmap='hot', cmin=1)
            plt.colorbar(h[3], ax=ax, label='Visit Count')
        
        title = title or f'Player {player_id} Movement Heatmap'
        ax.set_title(title, fontsize=16, fontweight='bold')
        
        path = self.output_dir / f'heatmap_player_{player_id}.png'
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"✓ Saved: {path}")
    
    def plot_all_players_heatmap(self, 
                                players_trajectories: Dict[int, List[Tuple[float, float]]],
                                title: str = 'All Players Movement'):
        """Plot heatmap of all players"""
        fig, ax = plt.subplots(figsize=(14, 10))
        self.plot_court(ax)
        
        # Combine all trajectories
        all_positions = []
        for player_id, trajectory in players_trajectories.items():
            all_positions.extend(trajectory)
        
        if all_positions:
            positions = np.array(all_positions)
            h = ax.hist2d(positions[:, 0], positions[:, 1], 
                         bins=25, cmap='YlOrRd', cmin=1)
            plt.colorbar(h[3], ax=ax, label='Total Visits')
        
        ax.set_title(title, fontsize=16, fontweight='bold')
        
        path = self.output_dir / 'heatmap_all_players.png'
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"✓ Saved: {path}")
    
    def plot_event_timeline(self,
                           events: List[Dict],
                           title: str = 'Game Events Timeline'):
        """
        Plot event timeline
        
        Args:
            events: List of event dicts with 'timestamp', 'event_type', 'player_id'
            title: Plot title
        """
        fig, ax = plt.subplots(figsize=(16, 6))
        
        if not events:
            ax.text(0.5, 0.5, 'No events', ha='center', va='center')
            plt.savefig(self.output_dir / 'timeline_events.png', dpi=150)
            plt.close()
            return
        
        # Separate events by type
        colors = {
            'pass': 'blue',
            'shot': 'red',
            'rebound': 'green',
            'turnover': 'orange',
            'steal': 'purple',
            'unknown': 'gray'
        }
        
        for event in events:
            event_type = event.get('event_type', 'unknown')
            timestamp = event.get('timestamp', 0)
            player_id = event.get('player_id', 0)
            
            color = colors.get(event_type, 'gray')
            ax.scatter(timestamp, player_id, s=100, alpha=0.6, 
                      color=color, label=event_type if event_type not in [e.get('event_type') for e in events[:events.index(event)]] else '')
        
        ax.set_xlabel('Time (seconds)', fontsize=12)
        ax.set_ylabel('Player ID', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        
        # Remove duplicate labels
        handles, labels = ax.get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        ax.legend(by_label.values(), by_label.keys(), loc='upper right')
        
        path = self.output_dir / 'timeline_events.png'
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"✓ Saved: {path}")
    
    def plot_distance_heatmap(self,
                             distance_matrix: np.ndarray,
                             player_ids: List[int],
                             title: str = 'Inter-player Distance Heatmap'):
        """
        Plot distance matrix heatmap
        
        Args:
            distance_matrix: NxN distance matrix
            player_ids: List of player IDs
            title: Plot title
        """
        fig, ax = plt.subplots(figsize=(10, 8))
        
        sns.heatmap(distance_matrix, cmap='YlOrRd', ax=ax, 
                   xticklabels=player_ids, yticklabels=player_ids,
                   cbar_kws={'label': 'Distance (meters)'})
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        
        path = self.output_dir / 'heatmap_distances.png'
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"✓ Saved: {path}")
    
    def plot_possession_timeline(self,
                                possession_data: List[Dict],
                                title: str = 'Possession Timeline'):
        """
        Plot possession timeline
        
        Args:
            possession_data: List of {'frame', 'timestamp', 'player_id', 'team'}
            title: Plot title
        """
        fig, ax = plt.subplots(figsize=(16, 6))
        
        if not possession_data:
            ax.text(0.5, 0.5, 'No possession data', ha='center', va='center')
            plt.savefig(self.output_dir / 'timeline_possession.png', dpi=150)
            plt.close()
            return
        
        timestamps = [p['timestamp'] for p in possession_data]
        player_ids = [p['player_id'] for p in possession_data]
        teams = [p.get('team', 'unknown') for p in possession_data]
        
        colors = {'green': '#2ecc71', 'white': '#ecf0f1', 'unknown': '#95a5a6'}
        color_list = [colors.get(team, '#95a5a6') for team in teams]
        
        ax.scatter(timestamps, player_ids, c=color_list, s=50, alpha=0.7)
        
        ax.set_xlabel('Time (seconds)', fontsize=12)
        ax.set_ylabel('Player ID', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        
        path = self.output_dir / 'timeline_possession.png'
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"✓ Saved: {path}")
    
    def plot_shot_distribution(self,
                              shots: List[Dict],
                              title: str = 'Shot Distribution'):
        """
        Plot shot locations on court
        
        Args:
            shots: List of shot dicts with 'position': (x, y), 'made': bool
            title: Plot title
        """
        fig, ax = plt.subplots(figsize=(14, 10))
        self.plot_court(ax)
        
        if shots:
            made_shots = [s for s in shots if s.get('made', False)]
            missed_shots = [s for s in shots if not s.get('made', False)]
            
            if made_shots:
                positions = np.array([s['position'] for s in made_shots])
                ax.scatter(positions[:, 0], positions[:, 1], 
                          c='green', s=200, marker='*', 
                          label=f'Made ({len(made_shots)})', edgecolors='darkgreen', linewidth=2)
            
            if missed_shots:
                positions = np.array([s['position'] for s in missed_shots])
                ax.scatter(positions[:, 0], positions[:, 1], 
                          c='red', s=150, marker='x', 
                          label=f'Missed ({len(missed_shots)})', linewidth=2)
        
        ax.set_title(title, fontsize=16, fontweight='bold')
        ax.legend(loc='upper right', fontsize=12)
        
        path = self.output_dir / 'shot_distribution.png'
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"✓ Saved: {path}")
    
    def plot_speed_over_time(self,
                            speeds: List[float],
                            timestamps: List[float],
                            player_id: int = None,
                            title: str = None):
        """
        Plot player speed over time
        
        Args:
            speeds: List of speed values
            timestamps: List of timestamps
            player_id: Player ID (optional)
            title: Plot title
        """
        fig, ax = plt.subplots(figsize=(16, 6))
        
        ax.plot(timestamps, speeds, linewidth=2, color='#3498db', label='Speed')
        ax.fill_between(timestamps, speeds, alpha=0.3, color='#3498db')
        
        # Add average line
        avg_speed = np.mean(speeds) if speeds else 0
        ax.axhline(avg_speed, color='red', linestyle='--', linewidth=2, 
                  label=f'Average: {avg_speed:.2f} m/s')
        
        ax.set_xlabel('Time (seconds)', fontsize=12)
        ax.set_ylabel('Speed (m/s)', fontsize=12)
        
        title = title or f'Player {player_id} Speed Over Time' if player_id else 'Speed Over Time'
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3)
        
        path = self.output_dir / f'speed_player_{player_id or "all"}.png'
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"✓ Saved: {path}")
    
    def plot_statistics_summary(self,
                               stats: Dict):
        """
        Plot statistics summary
        
        Args:
            stats: Dictionary with various statistics
        """
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle('Game Statistics Summary', fontsize=16, fontweight='bold')
        
        # Event counts
        events = stats.get('events', {})
        event_types = list(events.keys())
        event_counts = list(events.values())
        
        if event_types:
            axes[0, 0].bar(event_types, event_counts, color='#3498db')
            axes[0, 0].set_title('Event Distribution')
            axes[0, 0].set_ylabel('Count')
            axes[0, 0].tick_params(axis='x', rotation=45)
        
        # Player possessions
        possessions = stats.get('possessions', {})
        if possessions:
            player_ids = list(possessions.keys())
            poss_counts = list(possessions.values())
            axes[0, 1].bar(player_ids, poss_counts, color='#2ecc71')
            axes[0, 1].set_title('Possessions by Player')
            axes[0, 1].set_ylabel('Possession Count')
            axes[0, 1].set_xlabel('Player ID')
        
        # Shooting statistics
        shots = stats.get('shots', {})
        if shots and 'total_shots' in shots:
            shot_data = [shots.get('made', 0), shots.get('missed', 0)]
            axes[1, 0].pie(shot_data, labels=['Made', 'Missed'], autopct='%1.1f%%',
                          colors=['#2ecc71', '#e74c3c'])
            axes[1, 0].set_title('Shooting Efficiency')
        
        # Distance statistics
        distances = stats.get('distance', {})
        if distances and 'avg_teammate_distance' in distances:
            dist_types = ['Teammate', 'Opponent']
            dist_values = [
                distances.get('avg_teammate_distance', 0),
                distances.get('avg_opponent_distance', 0)
            ]
            axes[1, 1].bar(dist_types, dist_values, color=['#3498db', '#e74c3c'])
            axes[1, 1].set_title('Average Distances')
            axes[1, 1].set_ylabel('Distance (meters)')
        
        plt.tight_layout()
        
        path = self.output_dir / 'statistics_summary.png'
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"✓ Saved: {path}")
    
    def create_summary_report(self, all_visualizations: Dict[str, str]):
        """
        Create HTML summary of all visualizations
        
        Args:
            all_visualizations: Dict of {name: file_path}
        """
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>GradatumAI Visualization Report</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
                h1 { color: #2c3e50; text-align: center; }
                .container { max-width: 1200px; margin: 0 auto; }
                .viz-section { background: white; margin: 20px 0; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                .viz-section h2 { color: #3498db; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
                img { max-width: 100%; height: auto; border-radius: 4px; margin: 10px 0; }
                .timestamp { color: #7f8c8d; font-size: 12px; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🏀 GradatumAI Basketball Analysis Report</h1>
                <p class="timestamp">Generated: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """</p>
        """
        
        for section_name, img_path in all_visualizations.items():
            html += f"""
                <div class="viz-section">
                    <h2>{section_name}</h2>
                    <img src="{img_path}" alt="{section_name}">
                </div>
            """
        
        html += """
            </div>
        </body>
        </html>
        """
        
        report_path = self.output_dir / 'visualization_report.html'
        with open(report_path, 'w') as f:
            f.write(html)
        
        print(f"✓ Saved: {report_path}")


def main():
    """Example usage"""
    visualizer = BasketballVisualizer(output_dir='visualizations/')
    
    # Example data
    player_trajectories = {
        1: [(10 + i*0.5, 7 + np.sin(i*0.1)*1 for i in range(100))],
        2: [(15 + i*0.3, 7 + np.cos(i*0.1)*1 for i in range(100))],
    }
    
    # Create visualizations
    print("📊 Creating visualizations...")
    
    visualizer.plot_all_players_heatmap(player_trajectories)
    
    # Example events
    events = [
        {'timestamp': 5.0, 'event_type': 'pass', 'player_id': 1},
        {'timestamp': 8.5, 'event_type': 'shot', 'player_id': 2},
        {'timestamp': 12.0, 'event_type': 'rebound', 'player_id': 3},
    ]
    visualizer.plot_event_timeline(events)
    
    # Example shots
    shots = [
        {'position': (14.0, 7.5), 'made': True},
        {'position': (15.0, 8.0), 'made': False},
        {'position': (20.0, 7.5), 'made': True},
    ]
    visualizer.plot_shot_distribution(shots)
    
    # Statistics
    stats = {
        'events': {'pass': 25, 'shot': 8, 'rebound': 5, 'turnover': 4},
        'possessions': {1: 10, 2: 8, 3: 7},
        'shots': {'total_shots': 8, 'made': 3, 'missed': 5},
        'distance': {'avg_teammate_distance': 4.5, 'avg_opponent_distance': 3.2}
    }
    visualizer.plot_statistics_summary(stats)
    
    print("\n✅ Visualizations complete!")
    print(f"📁 Output directory: {visualizer.output_dir}")


if __name__ == '__main__':
    main()
