import streamlit as st
import pandas as pd
import statsapi
import pytz
from datetime import datetime

st.set_page_config(page_title="MLB AI Props Dashboard", layout="wide")
st.title("⚾ MLB Daily Matchup & AI Predictions (Phase 2)")

# --- 1. ZONA WAKTU ---
def get_mlb_date():
    wib_tz = pytz.timezone('Asia/Jakarta')
    now_est = datetime.now(wib_tz).astimezone(pytz.timezone('US/Eastern'))
    return now_est.strftime('%m/%d/%Y'), now_est.strftime('%Y-%m-%d')

mlb_date_str, mlb_date_api = get_mlb_date()
st.write(f"📅 **Jadwal Pertandingan (US Time):** {mlb_date_str}")

team_mapper = {
    "Arizona Diamondbacks": "ARI", "Atlanta Braves": "ATL", "Baltimore Orioles": "BAL",
    "Boston Red Sox": "BOS", "Chicago Cubs": "CHC", "Chicago White Sox": "CHW",
    "Cincinnati Reds": "CIN", "Cleveland Guardians": "CLE", "Colorado Rockies": "COL",
    "Detroit Tigers": "DET", "Houston Astros": "HOU", "Kansas City Royals": "KCR",
    "Los Angeles Angels": "LAA", "Los Angeles Dodgers": "LAD", "Miami Marlins": "MIA",
    "Milwaukee Brewers": "MIL", "Minnesota Twins": "MIN", "New York Mets": "NYM",
    "New York Yankees": "NYY", "Oakland Athletics": "OAK", "Philadelphia Phillies": "PHI",
    "Pittsburgh Pirates": "PIT", "San Diego Padres": "SDP", "San Francisco Giants": "SFG",
    "Seattle Mariners": "SEA", "St. Louis Cardinals": "STL", "Tampa Bay Rays": "TBR",
    "Texas Rangers": "TEX", "Toronto Blue Jays": "TOR", "Washington Nationals": "WSN"
}

# --- 2. FUNGSI TARIK DATA MATCH & CUACA (CACHE) ---
@st.cache_data(ttl=1800)
def get_daily_schedule():
    games = statsapi.schedule(date=mlb_date_str)
    playing_teams = []
    today_matchups = []
    player_to_team = {}
    game_details = []
    
    for game in games:
        away_abbr = team_mapper.get(game['away_name'], game['away_name'])
        home_abbr = team_mapper.get(game['home_name'], game['home_name'])
        
        playing_teams.extend([away_abbr, home_abbr])
        matchup_text = f"{away_abbr} @ {home_abbr} ({game.get('game_datetime', '')[11:16]} ET) - {game['status']}"
        today_matchups.append(matchup_text)
        
        # Ekstrak Info Pelempar (Probable Pitchers) dari jadwal
        away_p = game.get('away_probable_pitcher', 'TBD')
        home_p = game.get('home_probable_pitcher', 'TBD')
        venue = game.get('venue_name', 'Unknown Stadium')
        
        game_details.append({
            'game_id': game['game_id'],
            'status': game['status'],
            'away': away_abbr, 
            'home': home_abbr, 
            'text': matchup_text,
            'away_pitcher': away_p,
            'home_pitcher': home_p,
            'venue': venue
        })
        
        try:
            for p in statsapi.get('team_roster', {'teamId': game['away_id']})['roster']:
                player_to_team[p['person']['fullName']] = away_abbr
            for p in statsapi.get('team_roster', {'teamId': game['home_id']})['roster']:
                player_to_team[p['person']['fullName']] = home_abbr
        except: continue
            
    return playing_teams, today_matchups, player_to_team, game_details

@st.cache_data(ttl=3600)
def get_weather_info(game_id):
    try:
        game_data = statsapi.get('game', {'gamePk': game_id})['gameData']
        weather = game_data.get('weather', {})
        temp = weather.get('temp', 'N/A')
        condition = weather.get('condition', 'N/A')
        wind = weather.get('wind', 'N/A')
        return f"{temp}°F, {condition}", wind
    except:
        return "N/A", "N/A"

# --- 3. BACA DATA LOKAL ---
def load_local_data():
    try:
        df_hitters = pd.read_csv('master_hitter_2026.csv')
        df_pitchers = pd.read_csv('master_pitcher_2026.csv')
        return df_hitters, df_pitchers
    except Exception as e:
        st.error("⚠️ File CSV belum ada! Pastikan Fase 1 di GitHub Actions sudah selesai berjalan.")
        return pd.DataFrame(), pd.DataFrame()

# --- 4. LIVE BOXSCORE API (TAB 5 & 6) ---
@st.cache_data(ttl=300)
def get_live_boxscore(game_id, away_abbr, home_abbr):
    try:
        raw_data = statsapi.get('game_boxscore', {'gamePk': game_id})
        teams_data = raw_data.get('teams', {})
        hitters, pitchers = [], []
        
        for side, abbr in [('away', away_abbr), ('home', home_abbr)]:
            players = teams_data.get(side, {}).get('players', {})
            for pid, pdata in players.items():
                name = pdata.get('person', {}).get('fullName', 'Unknown')
                b_stats = pdata.get('stats', {}).get('batting', {})
                p_stats = pdata.get('stats', {}).get('pitching', {})
                
                if b_stats and b_stats.get('plateAppearances', 0) > 0:
                    hitters.append({
                        'Team': abbr, 'Name': name,
                        'AB': b_stats.get('atBats', 0), 'R': b_stats.get('runs', 0),
                        'H': b_stats.get('hits', 0), 'HR': b_stats.get('homeRuns', 0),
                        'RBI': b_stats.get('rbi', 0), 
                        'TB': b_stats.get('totalBases', b_stats.get('hits', 0))
                    })
                if p_stats and p_stats.get('battersFaced', 0) > 0:
                    ip = str(p_stats.get('inningsPitched', '0.0'))
                    pitchers.append({
                        'Team': abbr, 'Name': name, 'IP': ip,
                        'H Allowed': p_stats.get('hits', 0), 'R Allowed': p_stats.get('runs', 0),
                        'SO': p_stats.get('strikeOuts', 0)
                    })
        return pd.DataFrame(hitters), pd.DataFrame(pitchers)
    except:
        return pd.DataFrame(), pd.DataFrame()

playing_teams, today_matchups, player_team_map, game_details = get_daily_schedule()
df_hitters, df_pitchers = load_local_data()

if not df_hitters.empty: df_hitters.insert(1, 'Team', df_hitters['Name'].map(player_team_map))
if not df_pitchers.empty: df_pitchers.insert(1, 'Team', df_pitchers['Name'].map(player_team_map))

# --- UI DASHBOARD ---
if not today_matchups:
    st.warning("Tidak ada jadwal pertandingan MLB untuk hari ini.")
else:
    st.markdown("### 🏟️ Slate Summary (Pertandingan Hari Ini)")
    cols = st.columns(min(len(today_matchups), 6))
    for i, m in enumerate(today_matchups): cols[i % 6].info(m)

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Pitcher Matchups", 
        "Hitter Props", 
        "🔥 Daily Top Picks",
        "🚀 AI Predictions",
        "📡 Live Report",
        "📈 AI Tracker"
    ])

    with tab1:
        st.subheader("Pitcher Metrics Allowed")
        if not df_pitchers.empty:
            df_p_today = df_pitchers[df_pitchers['Team'].isin(playing_teams)].dropna(subset=['Team'])
            allowed_metrics = [c for c in ['xwOBA Allowed', 'xSLG Allowed', 'xBA Allowed', 'HardHit% Allowed', 'Barrel% Allowed'] if c in df_p_today.columns]
            st.dataframe(df_p_today.style.background_gradient(cmap='RdYlGn', subset=allowed_metrics) if allowed_metrics else df_p_today, use_container_width=True, height=500)

    with tab2:
        st.subheader("Hitter Advanced & Platoon Metrics")
        if not df_hitters.empty:
            df_h_today = df_hitters[df_hitters['Team'].isin(playing_teams)].dropna(subset=['Team'])
            col1, col2 = st.columns(2)
            with col1: search_name = st.text_input("🔍 Ketik Nama Pemain (Opsional):", "")
            with col2: 
                avail_teams = sorted(df_h_today['Team'].unique().tolist())
                sel_team = st.selectbox("Filter Berdasarkan Tim:", ["Semua Tim"] + avail_teams)
            
            if search_name: display_df = df_h_today[df_h_today['Name'].str.contains(search_name, case=False, na=False)]
            elif sel_team != "Semua Tim": display_df = df_h_today[df_h_today['Team'] == sel_team]
            else: display_df = df_h_today.sort_values(by='xwOBA', ascending=False).head(50)
            
            # Dinamis mengambil semua kolom statistik termasuk vs_L dan vs_R
            hitter_metrics = [c for c in display_df.columns if any(k in c for k in ['xwOBA', 'xBA', 'xSLG', 'HardHit', 'Barrel', 'SweetSpot'])]
            st.dataframe(display_df.style.background_gradient(cmap='RdYlGn', subset=hitter_metrics) if hitter_metrics else display_df, use_container_width=True, height=500)

    with tab3:
        st.subheader("🤖 Rekomendasi Pick Per Pertandingan")
        if not df_hitters.empty and not df_pitchers.empty:
            df_h_today = df_hitters[df_hitters['Team'].isin(playing_teams)].dropna(subset=['Team'])
            df_p_today = df_pitchers[df_pitchers['Team'].isin(playing_teams)].dropna(subset=['Team'])
            
            for game in game_details:
                with st.expander(f"⚾ Matchup: {game['text']}", expanded=False):
                    # --- BANNER STADION & PITCHER ---
                    weather_cond, wind_cond = get_weather_info(game['game_id'])
                    st.markdown(f"**🏟️ {game['venue']}** | 🌤️ **Cuaca:** {weather_cond} | 💨 **Angin:** {wind_cond}")
                    st.markdown(f"⚾ **Probable Pitchers:** {game['away_pitcher']} (Away) vs {game['home_pitcher']} (Home)")
                    st.divider()
                    
                    game_teams = [game['away'], game['home']]
                    h_df = df_h_today[df_h_today['Team'].isin(game_teams)]
                    p_df = df_p_today[df_p_today['Team'].isin(game_teams)]
                    if h_df.empty or p_df.empty: continue
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"### 🏏 Hitter Picks")
                        if 'Barrel%' in h_df.columns: st.success(f"**1. Over HR:** {h_df.sort_values(by='Barrel%', ascending=False).iloc[0]['Name']}")
                        if 'xSLG' in h_df.columns: st.info(f"**2. Over Total Base:** {h_df.sort_values(by='xSLG', ascending=False).iloc[0]['Name']}")
                        if 'xBA' in h_df.columns: st.caption(f"**3. Over Hit:** {h_df.sort_values(by='xBA', ascending=False).iloc[0]['Name']}")

                    with col2:
                        st.markdown("### 🎯 Pitcher Picks (O/U)")
                        if 'xwOBA Allowed' in p_df.columns:
                            st.success(f"**1. OVER Outs Recorded:** {p_df.sort_values(by='xwOBA Allowed', ascending=True).iloc[0]['Name']}")
                            st.error(f"**2. UNDER Outs Recorded:** {p_df.sort_values(by='xwOBA Allowed', ascending=False).iloc[0]['Name']}")

    with tab4:
        st.subheader("🚀 AI Prop Probability Model & Platoon Splits")
        if not df_hitters.empty:
            df_h_today = df_hitters[df_hitters['Team'].isin(playing_teams)].dropna(subset=['Team'])
            if 'HR_Prob_Score' in df_h_today.columns:
                for game in game_details:
                    with st.expander(f"🔥 AI Prediction: {game['text']}", expanded=False):
                        # --- BANNER STADION & PITCHER ---
                        weather_cond, wind_cond = get_weather_info(game['game_id'])
                        st.markdown(f"**🏟️ {game['venue']}** | 🌤️ **Cuaca:** {weather_cond} | 💨 **Angin:** {wind_cond}")
                        st.markdown(f"⚾ **Probable Pitchers:** {game['away_pitcher']} (Away) vs {game['home_pitcher']} (Home)")
                        st.divider()

                        col_away, col_home = st.columns(2)
                        
                        # --- AWAY TEAM ---
                        with col_away:
                            st.markdown(f"#### 🏟️ {game['away']} (Lawan {game['home_pitcher']})")
                            away_df = df_h_today[df_h_today['Team'] == game['away']]
                            if not away_df.empty:
                                hr_cols = ['Name', 'HR_Prob_Score'] + [c for c in ['xwOBA_vs_L', 'xwOBA_vs_R'] if c in away_df.columns]
                                hit_cols = ['Name', 'Hit_Prob_Score'] + [c for c in ['xBA_vs_L', 'xBA_vs_R'] if c in away_df.columns]
                                
                                st.write("🎯 **Top 5 HR Index & Platoon:**")
                                st.dataframe(away_df.sort_values('HR_Prob_Score', ascending=False).head(5)[hr_cols], hide_index=True, use_container_width=True)
                                
                                st.write("🏏 **Top 5 Hit Index & Platoon:**")
                                st.dataframe(away_df.sort_values('Hit_Prob_Score', ascending=False).head(5)[hit_cols], hide_index=True, use_container_width=True)

                        # --- HOME TEAM ---
                        with col_home:
                            st.markdown(f"#### 🏠 {game['home']} (Lawan {game['away_pitcher']})")
                            home_df = df_h_today[df_h_today['Team'] == game['home']]
                            if not home_df.empty:
                                hr_cols = ['Name', 'HR_Prob_Score'] + [c for c in ['xwOBA_vs_L', 'xwOBA_vs_R'] if c in home_df.columns]
                                hit_cols = ['Name', 'Hit_Prob_Score'] + [c for c in ['xBA_vs_L', 'xBA_vs_R'] if c in home_df.columns]
                                
                                st.write("🎯 **Top 5 HR Index & Platoon:**")
                                st.dataframe(home_df.sort_values('HR_Prob_Score', ascending=False).head(5)[hr_cols], hide_index=True, use_container_width=True)
                                
                                st.write("🏏 **Top 5 Hit Index & Platoon:**")
                                st.dataframe(home_df.sort_values('Hit_Prob_Score', ascending=False).head(5)[hit_cols], hide_index=True, use_container_width=True)
            else:
                st.warning("⚠️ Menunggu Fase 1 (Platoon CSV) selesai di-generate...")

    # --- TAB 5 & 6 (LIVE REPORT & TRACKER) TETAP SAMA ---
    with tab5:
        st.subheader("📡 Live Report & Hasil Pemain Hari Ini")
        for game in game_details:
            if game['status'] in ['Scheduled', 'Pre-Game', 'Warmup']: continue
            with st.expander(f"🔥 {game['text']}", expanded=False):
                live_h, live_p = get_live_boxscore(game['game_id'], game['away'], game['home'])
                if not live_h.empty:
                    sukses_h = live_h[(live_h['H'] >= 1) | (live_h['HR'] >= 1) | (live_h['TB'] >= 1)]
                    st.dataframe(sukses_h.sort_values(by=['TB', 'H'], ascending=False), hide_index=True, use_container_width=True)

    with tab6:
        st.subheader("📈 AI Model Accuracy & Slip Tracker (22 Picks)")
        if not df_hitters.empty:
            df_h_today = df_hitters[df_hitters['Team'].isin(playing_teams)].dropna(subset=['Team'])
            for game in game_details:
                if game['status'] in ['Scheduled', 'Pre-Game', 'Warmup']: continue
                with st.expander(f"📊 Slip Verification: {game['text']}", expanded=False):
                    live_h, _ = get_live_boxscore(game['game_id'], game['away'], game['home'])
                    h_df = df_h_today[df_h_today['Team'].isin([game['away'], game['home']])]
                    
                    if not live_h.empty and not h_df.empty and 'HR_Prob_Score' in h_df.columns:
                        targets = []
                        for team_abbr in [game['away'], game['home']]:
                            team_df = h_df[h_df['Team'] == team_abbr]
                            if not team_df.empty:
                                for _, row in team_df.sort_values('HR_Prob_Score', ascending=False).head(5).iterrows():
                                    targets.append({'name': row['Name'], 'team': team_abbr, 'prop': '🔥 Top 5 HR Index'})
                                for _, row in team_df.sort_values('Hit_Prob_Score', ascending=False).head(5).iterrows():
                                    targets.append({'name': row['Name'], 'team': team_abbr, 'prop': '🏏 Top 5 Hit Index'})
                                    
                        verification_rows = []
                        for t in targets:
                            p_live = live_h[live_h['Name'] == t['name']]
                            if not p_live.empty:
                                act_h, act_hr = int(p_live.iloc[0]['H']), int(p_live.iloc[0]['HR'])
                                status = "✅ WIN" if (('HR' in t['prop'] and act_hr >= 1) or ('Hit' in t['prop'] and act_h >= 1)) else ("⏳ LIVE" if game['status'] != 'Final' else "❌ MISS")
                                field_result = f"Hit: {act_h} | HR: {act_hr}"
                            else:
                                status, field_result = ("⏳ Belum Batting" if game['status'] != 'Final' else "❌ MISS (DNP)"), "Hit: 0 | HR: 0"
                                
                            verification_rows.append({'Tim': t['team'], 'Pemain': t['name'], 'Proyeksi': t['prop'], 'Hasil': field_result, 'Status': status})
                        st.dataframe(pd.DataFrame(verification_rows), hide_index=True, use_container_width=True)
