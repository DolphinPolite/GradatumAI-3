Kullanım Örnekleri
1. Temel Mesafe Hesaplama
pythonfrom distance_analyzer import DistanceAnalyzer

# Setup
analyzer = DistanceAnalyzer(
    pixel_to_meter=0.1,  # Kalibrasyona göre ayarla
    court_width_meters=28.0,
    court_length_meters=15.0,
    proximity_threshold=3.0
)

# İki oyuncu arası mesafe
distance = analyzer.calculate_pairwise_distance(player1, player2, timestamp=100)
print(f"Distance: {distance:.2f} meters")

# Tüm çiftler
all_pairs = analyzer.get_all_pairwise_distances(players, timestamp=100)
for pair in all_pairs:
    print(f"P{pair.player1_id} - P{pair.player2_id}: {pair.distance:.2f}m "
          f"(Same team: {pair.same_team})")
2. Proximity Analizi (Bir Oyuncu için)
python# Bir oyuncunun tüm diğer oyuncularla ilişkisi
info = analyzer.get_proximity_info(player, all_players, timestamp=100)

print(f"\nPlayer {info.player_id} Proximity:")
print(f"  Closest teammate: #{info.closest_teammate} "
      f"({info.closest_teammate_distance:.2f}m)")
print(f"  Closest opponent: #{info.closest_opponent} "
      f"({info.closest_opponent_distance:.2f}m)")
print(f"  Teammates within 3m: {len(info.teammates_within_3m)}")
print(f"  Opponents within 3m: {len(info.opponents_within_3m)}")
3. Takım Spacing Analizi
python# Takım formasyonu analizi
spacing = analyzer.get_team_spacing(players, team='green', timestamp=100)

print(f"\nTeam Spacing Metrics:")
print(f"  Average spacing: {spacing['avg_spacing']:.2f}m")
print(f"  Min spacing: {spacing['min_spacing']:.2f}m")
print(f"  Max spacing: {spacing['max_spacing']:.2f}m")
print(f"  Spread X: {spacing['spread_x']:.2f}m")
print(f"  Spread Y: {spacing['spread_y']:.2f}m")
print(f"  Team centroid: {spacing['centroid']}")
4. Savunma Baskısı Analizi
python# Hücum oyuncusuna yapılan baskı
offensive_player = players[0]  # Top taşıyan oyuncu
defensive_players = [p for p in players if p.team != offensive_player.team]

pressure = analyzer.get_defensive_pressure(
    offensive_player, defensive_players, timestamp=100
)

print(f"\nDefensive Pressure on Player {offensive_player.ID}:")
print(f"  Closest defender: #{pressure['closest_defender']} "
      f"({pressure['closest_defender_distance']:.2f}m)")
print(f"  Defenders within 2m: {len(pressure['defenders_within_2m'])}")
print(f"  Pressure score: {pressure['pressure_score']:.2f}")
5. Dijital İkiz için DataFrame Export
python# Tüm mesafe verilerini DataFrame'e çevir
df_distances = analyzer.export_to_dataframe(
    players, 
    start_timestamp=0, 
    end_timestamp=1000
)

print(df_distances.head())
# timestamp | player1_id | player2_id | distance | same_team | ...
# 0         | 1          | 2          | 3.45     | True      | ...
# 0         | 1          | 3          | 5.67     | False     | ...

# ML modeli için kaydet
df_distances.to_csv('player_distances.csv', index=False)

# Proximity bilgileri
df_proximity = analyzer.export_proximity_to_dataframe(
    players,
    start_timestamp=0,
    end_timestamp=1000
)

df_proximity.to_csv('player_proximity.csv', index=False)
6. Video Processing Loop'a Entegrasyon
pythonimport cv2
from feet_detector import FeetDetector
from distance_analyzer import DistanceAnalyzer

feet_detector = FeetDetector(players)
distance_analyzer = DistanceAnalyzer(pixel_to_meter=0.1)

cap = cv2.VideoCapture("basketball_game.mp4")
timestamp = 0

# Mesafe verilerini saklamak için
all_distance_data = []

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break
    
    # 1. Oyuncu pozisyonlarını güncelle
    frame, map_2d, map_2d_text = feet_detector.get_players_pos(
        M, M1, frame, timestamp, map_2d
    )
    
    # 2. Mesafe analizleri
    all_pairs = distance_analyzer.get_all_pairwise_distances(players, timestamp)
    all_distance_data.extend(all_pairs)
    
    # 3. Her oyuncu için proximity
    for player in players:
        if player.team != 'referee':
            info = distance_analyzer.get_proximity_info(player, players, timestamp)
            
            if info and timestamp in player.positions:
                pos = player.positions[timestamp]
                
                # En yakın rakibi göster
                if info.closest_opponent_distance:
                    text = f"D:{info.closest_opponent_distance:.1f}m"
                    cv2.putText(frame, text,
                               (pos[0], pos[1] + 20),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                               (0, 0, 255), 1)
    
    # 4. Takım spacing'i göster
    for team in ['green', 'white']:
        spacing = distance_analyzer.get_team_spacing(players, team, timestamp)
        if spacing:
            print(f"Frame {timestamp} - {team} spacing: "
                  f"{spacing['avg_spacing']:.2f}m")
    
    timestamp += 1
    
    # Her 100 frame'de cache temizle (memory)
    if timestamp % 100 == 0:
        distance_analyzer.clear_cache()
    
    cv2.imshow("Frame", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()

# Maç sonu analiz
df = pd.DataFrame([{
    'timestamp': p.timestamp,
    'p1': p.player1_id,
    'p2': p.player2_id,
    'dist': p.distance,
    'same_team': p.same_team
} for p in all_distance_data])

df.to_csv('match_distances.csv', index=False)

Dijital İkiz için Öneriler
Çıkarılacak Özellikler (Features):
python# Her frame için her oyuncu
features = {
    # Pozisyon
    'x': player.positions[t][0],
    'y': player.positions[t][1],
    
    # Proximity
    'closest_teammate_dist': info.closest_teammate_distance,
    'closest_opponent_dist': info.closest_opponent_distance,
    'teammates_within_3m': len(info.teammates_within_3m),
    'opponents_within_3m': len(info.opponents_within_3m),
    
    # Takım spacing
    'team_avg_spacing': spacing['avg_spacing'],
    'team_spread_x': spacing['spread_x'],
    'team_spread_y': spacing['spread_y'],
    
    # Hız (VelocityAnalyzer'dan)
    'speed': velocity,
    'acceleration': acceleration,
    
    # Savunma baskısı
    'defensive_pressure': pressure['pressure_score']
}
Bu özellikler ML modellerine (LSTM, Transformer, GNN) input olarak verilebilir!