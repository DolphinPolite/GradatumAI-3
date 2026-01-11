"""
Basketball Analytics - Data Export Module
Tüm pipeline çıktılarını kaydetme ve analiz sistemi
"""

import json
import csv
import os
from typing import Dict, List, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import pandas as pd
import numpy as np


@dataclass
class PlayerFrameData:
    """Bir oyuncunun bir frame'deki durumu"""
    frame_id: int
    timestamp: float
    player_id: int
    team: str
    team_player_id: int  # Takım içi ID (1-5)
    position_x: float
    position_y: float
    speed: float
    acceleration: float
    movement_state: str
    has_ball: bool
    closest_opponent_id: int = None
    distance_to_opponent: float = None


@dataclass
class EventData:
    """Olay kaydı"""
    frame_id: int
    timestamp: float
    event_type: str
    player_id: int
    team: str
    team_player_id: int
    details: Dict[str, Any]


@dataclass
class GameSummary:
    """Maç özet istatistikleri"""
    total_frames: int
    duration_seconds: float
    team_a_players: List[int]
    team_b_players: List[int]
    total_events: int
    events_by_type: Dict[str, int]
    ball_possession: Dict[str, float]  # Takım bazında top kontrolü


class DataExporter:
    """
    Pipeline sonuçlarını kaydetme ve analiz sınıfı.
    
    Özellikler:
    - Frame-by-frame player data
    - Event tracking
    - Team-based organization
    - Multiple export formats (JSON, CSV, Excel)
    - Real-time statistics
    """
    
    def __init__(self, output_dir: str = "output"):
        """
        Args:
            output_dir: Çıktı klasörü
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # Data storage
        self.player_frames: List[PlayerFrameData] = []
        self.events: List[EventData] = []
        
        # Team mapping (ID -> team, team_id)
        self.team_mapping: Dict[int, tuple] = {}
        
        # Statistics
        self.ball_possession_frames = {'green': 0, 'white': 0, None: 0}
        self.total_frames = 0
        
        print(f"📁 Data Exporter initialized: {output_dir}/")
    
    def update_team_mapping(self, players: Dict[int, Dict]):
        """
        Oyuncu-takım eşleşmesini güncelle.
        
        Her oyuncuya takım içi ID atar (1-5).
        """
        for pid, pdata in players.items():
            if pid not in self.team_mapping:
                team = pdata.get('team')
                
                # Takım içi ID hesapla
                team_players = [p for p, (t, _) in self.team_mapping.items() if t == team]
                team_player_id = len(team_players) + 1
                
                self.team_mapping[pid] = (team, team_player_id)
    
    def collect_frame(self, frame_data: Dict):
        """
        Bir frame'in verilerini topla.
        
        Args:
            frame_data: Pipeline'dan gelen frame verisi
        """
        try:
            frame_id = int(frame_data.get('frame_id', 0))
            timestamp = float(frame_data.get('timestamp', 0.0))
            players = frame_data.get('players', {})
            
            # Team mapping güncelle
            self.update_team_mapping(players)
            
            # Player data
            for pid, pdata in players.items():
                try:
                    team, team_player_id = self.team_mapping.get(pid, ('unknown', 0))
                    
                    pos = pdata.get('position_2d', (0, 0))
                    
                    # None check ve safe conversion
                    def safe_float(val, default=0.0):
                        if val is None:
                            return default
                        try:
                            return float(val)
                        except (ValueError, TypeError):
                            return default
                    
                    def safe_int(val, default=None):
                        if val is None:
                            return default
                        try:
                            return int(val)
                        except (ValueError, TypeError):
                            return default
                    
                    # NumPy tiplerini Python tiplerine dönüştür
                    player_frame = PlayerFrameData(
                        frame_id=int(frame_id),
                        timestamp=float(timestamp),
                        player_id=int(pid),
                        team=str(team),
                        team_player_id=int(team_player_id),
                        position_x=safe_float(pos[0]) if pos and len(pos) > 0 else 0.0,
                        position_y=safe_float(pos[1]) if pos and len(pos) > 1 else 0.0,
                        speed=safe_float(pdata.get('speed', 0.0)),
                        acceleration=safe_float(pdata.get('acceleration', 0.0)),
                        movement_state=str(pdata.get('movement_state', 'unknown')),
                        has_ball=bool(pdata.get('has_ball', False)),
                        closest_opponent_id=safe_int(pdata.get('closest_player_id')),
                        distance_to_opponent=safe_float(pdata.get('min_distance')) if pdata.get('min_distance') is not None else None
                    )
                    
                    self.player_frames.append(player_frame)
                    
                    # Ball possession tracking
                    if pdata.get('has_ball'):
                        self.ball_possession_frames[team] += 1
                
                except Exception as e:
                    print(f"⚠️  Warning: Failed to collect player {pid} data: {e}")
                    continue
            
            # Events
            for event in frame_data.get('events', []):
                try:
                    pid = event.get('player_id')
                    if pid is None:
                        continue
                        
                    team, team_player_id = self.team_mapping.get(pid, ('unknown', 0))
                    
                    # Details'i JSON-safe yap
                    details = event.get('details', {})
                    safe_details = self._convert_to_json_safe(details)
                    
                    event_data = EventData(
                        frame_id=int(frame_id),
                        timestamp=float(timestamp),
                        event_type=str(event.get('type', 'unknown')),
                        player_id=int(pid),
                        team=str(team),
                        team_player_id=int(team_player_id),
                        details=safe_details
                    )
                    
                    self.events.append(event_data)
                
                except Exception as e:
                    print(f"⚠️  Warning: Failed to collect event: {e}")
                    continue
            
            self.total_frames += 1
        
        except Exception as e:
            print(f"⚠️  Warning: Failed to collect frame {frame_data.get('frame_id', '?')}: {e}")
            import traceback
            traceback.print_exc()
    
    def export_json(self, filename: str = None):
        """JSON formatında kaydet"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"game_data_{timestamp}.json"
        
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            data = {
                'metadata': self._get_metadata(),
                'team_mapping': {
                    str(pid): {'team': str(team), 'team_player_id': int(tid)}
                    for pid, (team, tid) in self.team_mapping.items()
                },
                'player_frames': [self._convert_to_json_safe(asdict(pf)) for pf in self.player_frames],
                'events': [self._convert_to_json_safe(asdict(e)) for e in self.events],
                'summary': self._convert_to_json_safe(asdict(self._get_summary()))
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ JSON saved: {filepath}")
            return filepath
        
        except Exception as e:
            print(f"❌ JSON export failed: {e}")
            import traceback
            traceback.print_exc()
            
            # Try minimal export as fallback
            try:
                print("   Attempting minimal export...")
                minimal_data = {
                    'metadata': self._get_metadata(),
                    'summary': self._convert_to_json_safe(asdict(self._get_summary()))
                }
                fallback_path = filepath.replace('.json', '_minimal.json')
                with open(fallback_path, 'w', encoding='utf-8') as f:
                    json.dump(minimal_data, f, indent=2, ensure_ascii=False)
                print(f"✅ Minimal JSON saved: {fallback_path}")
                return fallback_path
            except Exception as e2:
                print(f"❌ Minimal export also failed: {e2}")
                return None
    
    def export_csv(self):
        """CSV formatında kaydet (çoklu dosya)"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        try:
            # 1. Player frames CSV
            if self.player_frames:
                df_players = pd.DataFrame([asdict(pf) for pf in self.player_frames])
                players_file = os.path.join(self.output_dir, f"player_data_{timestamp}.csv")
                df_players.to_csv(players_file, index=False, encoding='utf-8')
                print(f"✅ Player CSV saved: {players_file}")
            else:
                print("⚠️  No player data to export")
                players_file = None
            
            # 2. Events CSV
            if self.events:
                events_data = []
                for event in self.events:
                    try:
                        row = asdict(event)
                        # Details'i flatten et
                        details = row.pop('details')
                        if isinstance(details, dict):
                            for key, value in details.items():
                                # Convert to JSON-safe values
                                if isinstance(value, (np.integer, np.int32, np.int64)):
                                    value = int(value)
                                elif isinstance(value, (np.floating, np.float32, np.float64)):
                                    value = float(value)
                                row[f'detail_{key}'] = value
                        events_data.append(row)
                    except Exception as e:
                        print(f"⚠️  Warning: Skipping event due to error: {e}")
                        continue
                
                if events_data:
                    df_events = pd.DataFrame(events_data)
                    events_file = os.path.join(self.output_dir, f"events_{timestamp}.csv")
                    df_events.to_csv(events_file, index=False, encoding='utf-8')
                    print(f"✅ Events CSV saved: {events_file}")
                else:
                    print("⚠️  No valid events to export")
                    events_file = None
            else:
                print("⚠️  No events to export")
                events_file = None
            
            # 3. Summary CSV
            summary = self._get_summary()
            summary_file = os.path.join(self.output_dir, f"summary_{timestamp}.csv")
            with open(summary_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Metric', 'Value'])
                writer.writerow(['Total Frames', summary.total_frames])
                writer.writerow(['Duration (s)', f"{summary.duration_seconds:.2f}"])
                writer.writerow(['Total Events', summary.total_events])
                writer.writerow(['Team A Players', ', '.join(map(str, summary.team_a_players))])
                writer.writerow(['Team B Players', ', '.join(map(str, summary.team_b_players))])
                writer.writerow(['', ''])
                writer.writerow(['Event Type', 'Count'])
                for etype, count in summary.events_by_type.items():
                    writer.writerow([etype, count])
                writer.writerow(['', ''])
                writer.writerow(['Ball Possession', 'Percentage'])
                for team, pct in summary.ball_possession.items():
                    writer.writerow([team.upper(), f"{pct:.1f}%"])
            
            print(f"✅ Summary CSV saved: {summary_file}")
            
            return players_file, events_file, summary_file
        
        except Exception as e:
            print(f"❌ CSV export failed: {e}")
            import traceback
            traceback.print_exc()
            return None, None, None
    
    def export_excel(self, filename: str = None):
        """Excel formatında kaydet (çoklu sheet)"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"game_analysis_{timestamp}.xlsx"
        
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                # Sheet 1: Player Data
                if self.player_frames:
                    df_players = pd.DataFrame([asdict(pf) for pf in self.player_frames])
                    df_players.to_excel(writer, sheet_name='Player Data', index=False)
                
                # Sheet 2: Events
                if self.events:
                    events_data = []
                    for event in self.events:
                        try:
                            row = asdict(event)
                            details = row.pop('details')
                            if isinstance(details, dict):
                                for key, value in details.items():
                                    if isinstance(value, (np.integer, np.int32, np.int64)):
                                        value = int(value)
                                    elif isinstance(value, (np.floating, np.float32, np.float64)):
                                        value = float(value)
                                    row[f'detail_{key}'] = value
                            events_data.append(row)
                        except Exception as e:
                            print(f"⚠️  Skipping event: {e}")
                            continue
                    
                    if events_data:
                        df_events = pd.DataFrame(events_data)
                        df_events.to_excel(writer, sheet_name='Events', index=False)
                
                # Sheet 3: Team Mapping
                if self.team_mapping:
                    team_data = [
                        {
                            'Player ID': int(pid),
                            'Team': str(team),
                            'Team Player ID': int(tid),
                            'Display Name': f"{team.upper()} #{tid}"
                        }
                        for pid, (team, tid) in self.team_mapping.items()
                    ]
                    df_teams = pd.DataFrame(team_data)
                    df_teams.to_excel(writer, sheet_name='Team Mapping', index=False)
                
                # Sheet 4: Summary Statistics
                summary = self._get_summary()
                summary_data = [
                    {'Metric': 'Total Frames', 'Value': summary.total_frames},
                    {'Metric': 'Duration (seconds)', 'Value': f"{summary.duration_seconds:.2f}"},
                    {'Metric': 'Total Events', 'Value': summary.total_events},
                    {'Metric': 'Team A Players', 'Value': ', '.join(map(str, summary.team_a_players))},
                    {'Metric': 'Team B Players', 'Value': ', '.join(map(str, summary.team_b_players))},
                ]
                
                # Add ball possession
                for team, percentage in summary.ball_possession.items():
                    summary_data.append({
                        'Metric': f'{team.upper()} Ball Possession',
                        'Value': f'{percentage:.1f}%'
                    })
                
                df_summary = pd.DataFrame(summary_data)
                df_summary.to_excel(writer, sheet_name='Summary', index=False)
                
                # Sheet 5: Event Breakdown
                if summary.events_by_type:
                    event_breakdown = [
                        {'Event Type': etype, 'Count': count}
                        for etype, count in summary.events_by_type.items()
                    ]
                    df_event_breakdown = pd.DataFrame(event_breakdown)
                    df_event_breakdown.to_excel(writer, sheet_name='Event Breakdown', index=False)
            
            print(f"✅ Excel saved: {filepath}")
            return filepath
        
        except Exception as e:
            print(f"❌ Excel export failed: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def export_all(self):
        """Tüm formatlarda kaydet"""
        print("\n📊 Exporting data in all formats...")
        
        results = {
            'json': None,
            'csv': (None, None, None),
            'excel': None
        }
        
        # JSON Export
        try:
            results['json'] = self.export_json()
        except Exception as e:
            print(f"❌ JSON export failed: {e}")
            import traceback
            traceback.print_exc()
        
        # CSV Export
        try:
            results['csv'] = self.export_csv()
        except Exception as e:
            print(f"❌ CSV export failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Excel Export
        try:
            results['excel'] = self.export_excel()
        except Exception as e:
            print(f"❌ Excel export failed: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"\n✅ Export process complete!")
        
        # Count successful exports
        successful = 0
        if results['json']: successful += 1
        if any(results['csv']): successful += 1
        if results['excel']: successful += 1
        
        print(f"   Successful exports: {successful}/3")
        
        return results
    
    def print_summary(self):
        """Özet istatistikleri yazdır"""
        summary = self._get_summary()
        
        print("\n" + "="*70)
        print("GAME SUMMARY")
        print("="*70)
        
        print(f"\n📊 Basic Stats:")
        print(f"   Total Frames: {summary.total_frames}")
        print(f"   Duration: {summary.duration_seconds:.2f}s")
        print(f"   Total Events: {summary.total_events}")
        
        print(f"\n👥 Teams:")
        print(f"   Team A (green): {summary.team_a_players}")
        print(f"   Team B (white): {summary.team_b_players}")
        
        print(f"\n🏀 Ball Possession:")
        for team, percentage in summary.ball_possession.items():
            if team:
                print(f"   {team.upper():10s}: {percentage:5.1f}%")
        
        print(f"\n🎯 Events Breakdown:")
        for etype, count in sorted(summary.events_by_type.items(), 
                                   key=lambda x: x[1], reverse=True):
            print(f"   {etype:20s}: {count:4d}")
    
    def _get_metadata(self) -> Dict:
        """Metadata oluştur"""
        return {
            'export_time': datetime.now().isoformat(),
            'total_frames': self.total_frames,
            'total_players': len(self.team_mapping),
            'total_events': len(self.events)
        }
    
    def _get_summary(self) -> GameSummary:
        """Özet istatistikler oluştur"""
        # Team player lists
        team_a = [pid for pid, (team, _) in self.team_mapping.items() if team == 'green']
        team_b = [pid for pid, (team, _) in self.team_mapping.items() if team == 'white']
        
        # Event counts
        events_by_type = {}
        for event in self.events:
            events_by_type[event.event_type] = events_by_type.get(event.event_type, 0) + 1
        
        # Ball possession percentages
        total_possession_frames = sum(self.ball_possession_frames.values())
        ball_possession_pct = {
            team: (frames / total_possession_frames * 100) if total_possession_frames > 0 else 0
            for team, frames in self.ball_possession_frames.items()
            if team is not None
        }
        
        return GameSummary(
            total_frames=self.total_frames,
            duration_seconds=self.total_frames / 30.0,  # Assuming 30 FPS
            team_a_players=team_a,
            team_b_players=team_b,
            total_events=len(self.events),
            events_by_type=events_by_type,
            ball_possession=ball_possession_pct
        )
    
    def _convert_to_json_safe(self, obj):
        """NumPy ve diğer tipleri JSON-safe tiplere dönüştür"""
        
        if isinstance(obj, dict):
            return {key: self._convert_to_json_safe(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_to_json_safe(item) for item in obj]
        elif isinstance(obj, tuple):
            return [self._convert_to_json_safe(item) for item in obj]
        elif isinstance(obj, (np.integer, np.int32, np.int64)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float32, np.float64)):
            # Handle NaN and Inf
            if np.isnan(obj):
                return None
            elif np.isinf(obj):
                return None
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (np.bool_, bool)):
            return bool(obj)
        elif obj is None or isinstance(obj, (int, float, str)):
            # Handle Python float NaN and Inf
            if isinstance(obj, float):
                if np.isnan(obj) or np.isinf(obj):
                    return None
            return obj
        else:
            # Son çare: string'e çevir
            try:
                return str(obj)
            except:
                return None


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_exporter(output_dir: str = "output") -> DataExporter:
    """Factory function to create exporter"""
    return DataExporter(output_dir)


if __name__ == "__main__":
    print("📊 Basketball Analytics - Data Exporter")
    print("="*70)
    print("\nThis module handles data export and statistics.")
    print("Import and use in your pipeline!")