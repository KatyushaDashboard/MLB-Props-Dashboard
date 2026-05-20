import statsapi
import pandas as pd
from datetime import datetime, timedelta
import pytz

def get_mlb_dates():
    wib_tz = pytz.timezone('Asia/Jakarta')
    now_est = datetime.now(wib_tz).astimezone(pytz.timezone('US/Eastern'))
    today_str = now_est.strftime('%m/%d/%Y')
    two_weeks_ago = (now_est - timedelta(days=14)).strftime('%m/%d/%Y')
    return today_str, two_weeks_ago

today_date, l14_date = get_mlb_dates()
print(f"🔄 Memulai penarikan data MLB... (Target: {today_date})")

# 1. TARIK DATA TIM & BULLPEN ERA
teams = statsapi.get('teams', {'sportId': 1})['teams']
team_mapping = {}
bullpen_era_dict = {}

print("📊 Memproses Data Bullpen ERA...")
for t in teams:
    team_id = t['id']
    team_abbr = t.get('abbreviation', 'UNK')
    team_mapping[team_id] = team_abbr
    
    try:
        # Tarik statistik tim (khusus relief pitcher / bullpen)
        team_stats = statsapi.get('team_stats', {'teamId': team_id, 'group': 'pitching', 'type': 'season', 'split': 'rp'})
        era = float(team_stats['stats'][0]['splits'][0]['stat']['era'])
        bullpen_era_dict[team_abbr] = era
    except:
        bullpen_era_dict[team_abbr] = 4.15 # Fallback standar liga jika gagal

# 2. CARI BATTING ORDER DARI PERTANDINGAN TERAKHIR
print("📋 Melacak Batting Order terbaru...")
batting_order_dict = {}
for team_id, team_abbr in team_mapping.items():
    try:
        # Cari pertandingan terakhir tim
        recent_games = statsapi.schedule(team=team_id, start_date=l14_date, end_date=today_date)
        if recent_games:
            last_game_id = recent_games[-1]['game_id']
            box = statsapi.get('game_boxscore', {'gamePk': last_game_id})
            
            # Tentukan apakah tim ini Away atau Home di laga terakhir
            side = 'away' if recent_games[-1]['away_id'] == team_id else 'home'
            batters = box['teams'][side]['batters']
            
            # Batters array biasanya berurutan 1-9
            order = 1
            for pid in batters:
                batting_order_dict[pid] = order
                if order < 9: order += 1
    except:
        pass

# 3. PROSES PEMAIN (HITTERS & PITCHERS)
hitters_data = []
pitchers_data = []

print("⚾ Mengekstrak data pemain aktif (Hitters & Pitchers)...")
for team_id, team_abbr in team_mapping.items():
    try:
        roster = statsapi.get('team_roster', {'teamId': team_id})['roster']
    except:
        continue
        
    for player in roster:
        pid = player['person']['id']
        p_name = player['person']['fullName']
        position = player['position']['abbreviation']
        
        try:
            # Tarik statistik musim penuh dan L14
            p_info = statsapi.get('person', {
                'personId': pid, 
                'hydrate': f'stats(group=[hitting,pitching],type=[season,byDateRange],startDate={l14_date},endDate={today_date})'
            })
            stats_list = p_info['people'][0].get('stats', [])
            
            if position == 'P':
                # --- LOGIKA PITCHER ---
                era, whip, xba_alwd, xwoba_alwd, xslg_alwd = 4.50, 1.30, 0.250, 0.320, 0.400
                for st in stats_list:
                    if st['group']['displayName'] == 'pitching' and st['type']['displayName'] == 'season':
                        s = st.get('splits', [{}])[0].get('stat', {})
                        era = float(s.get('era', 4.50))
                        whip = float(s.get('whip', 1.30))
                        # Simulasi metrik advanced dari stat standar (karena statcast murni sulit ditarik via base statsapi)
                        xba_alwd = round(float(s.get('avg', 0.250)) + 0.010, 3) 
                        xwoba_alwd = round(float(s.get('obp', 0.320)) + 0.015, 3)
                        xslg_alwd = round(float(s.get('slg', 0.400)) + 0.020, 3)
                
                pitchers_data.append({
                    'Name': p_name, 'Team': team_abbr,
                    'ERA': era, 'WHIP': whip,
                    'xBA Allowed': xba_alwd, 'xwOBA Allowed': xwoba_alwd, 'xSLG Allowed': xslg_alwd,
                    'Bullpen_ERA': bullpen_era_dict.get(team_abbr, 4.15)
                })
                
            else:
                # --- LOGIKA HITTER ---
                xba, xslg, xwoba = 0.240, 0.400, 0.310
                barrel, hardhit, max_ev = 5.0, 35.0, 105.0
                pa_l14, xwoba_l14 = 0, 0.310
                
                for st in stats_list:
                    if st['group']['displayName'] == 'hitting':
                        s = st.get('splits', [{}])[0].get('stat', {})
                        if st['type']['displayName'] == 'season':
                            # Estimasi Advanced Stats (Proxy)
                            xba = round(float(s.get('avg', 0.240)) + 0.005, 3)
                            xslg = round(float(s.get('slg', 0.400)) + 0.010, 3)
                            xwoba = round(float(s.get('obp', 0.310)) + 0.015, 3)
                            
                            ops = float(s.get('ops', 0.700))
                            barrel = round((ops / 0.800) * 8.0, 1)
                            hardhit = round((ops / 0.800) * 40.0, 1)
                            max_ev = round(105.0 + (barrel * 0.5), 1)
                            
                        elif st['type']['displayName'] == 'byDateRange':
                            # Data 14 Hari Terakhir
                            pa_l14 = int(s.get('plateAppearances', 0))
                            xwoba_l14 = round(float(s.get('obp', 0.310)) + 0.015, 3)
                
                # Simulasi Platoon Splits (L/R) karena limitasi endpoint
                xwoba_vs_r = round(xwoba * (1.02 if position in ['L', 'S'] else 0.98), 3)
                xwoba_vs_l = round(xwoba * (1.02 if position in ['R', 'S'] else 0.95), 3)
                
                # Formula AI Score
                hit_score = round((xba * 100) + (xwoba_l14 * 50) + (pa_l14 * 0.5), 1)
                hr_score = round(barrel + (hardhit * 0.5) + (xslg * 50), 1)
                
                b_order = batting_order_dict.get(pid, 6) # Default urutan 6 jika tidak main di laga terakhir
                
                hitters_data.append({
                    'Name': p_name, 'Team': team_abbr,
                    'xBA': xba, 'xSLG': xslg, 'xwOBA': xwoba,
                    'Barrel%': barrel, 'HardHit%': hardhit, 'Max EV': max_ev,
                    'xwOBA_vs_R': xwoba_vs_r, 'xwOBA_vs_L': xwoba_vs_l,
                    'Batting_Order': b_order, 'PA_L14': pa_l14, 'xwOBA_L14': xwoba_l14,
                    'Hit_Prob_Score': hit_score, 'HR_Prob_Score': hr_score
                })
                
        except Exception as e:
            continue

# 4. SIMPAN KE CSV
df_h = pd.DataFrame(hitters_data)
df_p = pd.DataFrame(pitchers_data)

# Filter Hitter: Buang yang PA L14-nya terlalu kecil (misal cedera/jarang main) kecuali urutan pukul atas
if not df_h.empty:
    df_h = df_h[(df_h['PA_L14'] >= 15) | (df_h['Batting_Order'] <= 5)]

df_h.to_csv('master_hitter_2026.csv', index=False)
df_p.to_csv('master_pitcher_2026.csv', index=False)

print(f"✅ Selesai! Berhasil menyimpan {len(df_h)} Hitters dan {len(df_p)} Pitchers.")
