import streamlit as st
import pandas as pd
import statsapi
import pytz
from datetime import datetime

st.set_page_config(page_title="MLB Daily Props Dashboard", layout="wide")
st.title("⚾ MLB Daily Matchup & Props Dashboard (Pro Pipeline Edition)")

# --- 1. ZONA WAKTU ---
def get_mlb_date():
    wib_tz = pytz.timezone('Asia/Jakarta')
    now_est = datetime.now(wib_tz).astimezone(pytz.timezone('US/Eastern'))
    return now_est.strftime('%m/%d/%Y'), now_est.strftime('%Y-%m-%d')

mlb_date_str, mlb_date_api = get_mlb_date()
st.write(f"📅 **Jadwal Pertandingan (US Time):** {mlb_date_str}")

# --- 2. TARIK JADWAL LIVE ---
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
        matchup_text = f"{away_abbr} @ {home_abbr} ({game.get('game_datetime', '')[11:16]} ET)"
        today_matchups.append(matchup_text)
        game_details.append({'away': away_abbr, 'home': home_abbr, 'text': matchup_text})
        
        try:
            for p in statsapi.get('team_roster', {'teamId': game['away_id']})['roster']:
                player_to_team[p['person']['fullName']] = away_abbr
            for p in statsapi.get('team_roster', {'teamId': game['home_id']})['roster']:
                player_to_team[p['person']['fullName']] = home_abbr
        except: continue
            
    return playing_teams, today_matchups, player_to_team, game_details

# --- 3. BACA DATA LOKAL (Hancurkan Cache Di Sini Agar Data Selalu Fresh) ---
def load_local_data():
    try:
        df_hitters = pd.read_csv('master_hitter_2026.csv')
        df_pitchers = pd.read_csv('master_pitcher_2026.csv')
        return df_hitters, df_pitchers
    except Exception as e:
        st.error("⚠️ File CSV belum ada! Jalankan 'python bot_updater.py' di CMD terlebih dahulu.")
        return pd.DataFrame(), pd.DataFrame()

playing_teams, today_matchups, player_team_map, game_details = get_daily_schedule()
df_hitters, df_pitchers = load_local_data()

if not df_hitters.empty:
    df_hitters.insert(1, 'Team', df_hitters['Name'].map(player_team_map))
if not df_pitchers.empty:
    df_pitchers.insert(1, 'Team', df_pitchers['Name'].map(player_team_map))

# --- UI DASHBOARD ---
if not today_matchups:
    st.warning("Tidak ada jadwal pertandingan MLB untuk hari ini.")
else:
    st.markdown("### 🏟️ Slate Summary (Pertandingan Hari Ini)")
    cols = st.columns(min(len(today_matchups), 6))
    for i, m in enumerate(today_matchups): cols[i % 6].info(m)

    # RE-ESTABLISH 4 TABS UTAMA
    tab1, tab2, tab3, tab4 = st.tabs([
        "Pitcher Matchups (Allowed)", 
        "Hitter Props", 
        "🔥 Game-by-Game Picks",
        "🚀 AI Probability Predictions"
    ])

    # --- TAB 1: PITCHER ---
    with tab1:
        st.subheader("Pitcher Metrics Allowed (Statcast)")
        if not df_pitchers.empty:
            df_p_today = df_pitchers[df_pitchers['Team'].isin(playing_teams)].dropna(subset=['Team'])
            styled_pitchers = df_p_today.style
            
            allowed_metrics = [c for c in ['xwOBA Allowed', 'xSLG Allowed', 'xBA Allowed', 'HardHit% Allowed', 'Barrel% Allowed'] if c in df_p_today.columns]
            if allowed_metrics:
                styled_pitchers = styled_pitchers.background_gradient(cmap='RdYlGn', subset=allowed_metrics)
                
            st.dataframe(styled_pitchers, use_container_width=True, height=500)

    # --- TAB 2: HITTER ---
    with tab2:
        st.subheader("Hitter Advanced & Expected Metrics")
        if not df_hitters.empty:
            df_h_today = df_hitters[df_hitters['Team'].isin(playing_teams)].dropna(subset=['Team'])
            
            col1, col2 = st.columns(2)
            with col1:
                search_name = st.text_input("🔍 Ketik Nama Pemain (Opsional):", "")
            with col2:
                available_teams = sorted(df_h_today['Team'].unique().tolist())
                selected_team = st.selectbox("Atau Filter Berdasarkan Tim:", ["Semua Tim"] + available_teams)
            
            if search_name:
                display_df = df_h_today[df_h_today['Name'].str.contains(search_name, case=False, na=False)]
            elif selected_team != "Semua Tim":
                display_df = df_h_today[df_h_today['Team'] == selected_team]
            else:
                sort_col = 'xwOBA (14d)' if 'xwOBA (14d)' in df_h_today.columns else ('xwOBA' if 'xwOBA' in df_h_today.columns else df_h_today.columns[2])
                display_df = df_h_today.sort_values(by=sort_col, ascending=False).head(50)
            
            styled_hitters = display_df.style
            
            hitter_metrics = [c for c in ['xwOBA', 'xSLG', 'xBA', 'HardHit%', 'Barrel%', 'Max EV', 'SweetSpot% (14d)', 'HardHit% (14d)', 'Barrel% (14d)', 'xwOBA (14d)'] if c in display_df.columns]
            if hitter_metrics:
                styled_hitters = styled_hitters.background_gradient(cmap='RdYlGn', subset=hitter_metrics)
                
            st.dataframe(styled_hitters, use_container_width=True, height=500)

    # --- TAB 3: GAME-BY-GAME PICKS ---
    with tab3:
        st.subheader("🤖 Rekomendasi Pick Per Pertandingan")
        st.write("Daftar Pick terbaik yang diurutkan secara matematis untuk setiap pertandingan yang berjalan hari ini.")
        
        if not df_hitters.empty and not df_pitchers.empty:
            df_h_today = df_hitters[df_hitters['Team'].isin(playing_teams)].dropna(subset=['Team'])
            df_p_today = df_pitchers[df_pitchers['Team'].isin(playing_teams)].dropna(subset=['Team'])
            
            for game in game_details:
                with st.expander(f"⚾ Matchup: {game['text']}", expanded=False):
                    game_teams = [game['away'], game['home']]
                    h_df = df_h_today[df_h_today['Team'].isin(game_teams)]
                    p_df = df_p_today[df_p_today['Team'].isin(game_teams)]
                    
                    if h_df.empty or p_df.empty:
                        st.info("Sampel data pemain untuk pertandingan ini belum lengkap.")
                        continue
                        
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown(f"### 🏏 Hitter Picks ({game['away']} & {game['home']})")
                        
                        if 'Barrel%' in h_df.columns:
                            hr_pick = h_df.sort_values(by='Barrel%', ascending=False).iloc[0]
                            st.success(f"**1. Pick Over Home Run (HR):**\n{hr_pick['Name']} ({hr_pick['Team']}) - *Barrel: {hr_pick['Barrel%']}%*")
                        
                        if 'Max EV' in h_df.columns:
                            dark_hr = h_df.sort_values(by='Max EV', ascending=False).iloc[0]
                            st.success(f"**↳ Dark Horse HR (Max EV):** {dark_hr['Name']} ({dark_hr['Team']}) - *Pukulan Terkeras: {dark_hr['Max EV']} mph*")

                        if 'xSLG' in h_df.columns:
                            tb_pick = h_df.sort_values(by='xSLG', ascending=False).iloc[0]
                            sw_text = f" | SweetSpot (14d): {tb_pick['SweetSpot% (14d)']}%" if 'SweetSpot% (14d)' in h_df.columns else ""
                            st.info(f"**2. Pick Over Total Base:** {tb_pick['Name']} ({tb_pick['Team']}) - *xSLG: {tb_pick['xSLG']}{sw_text}*")
                            
                        if 'xwOBA' in h_df.columns:
                            run_pick = h_df.sort_values(by='xwOBA', ascending=False).iloc[0]
                            st.warning(f"**3. Pick Over Run:** {run_pick['Name']} ({run_pick['Team']}) - *xwOBA: {run_pick['xwOBA']} (Sering on-base)*")

                        if 'HardHit%' in h_df.columns:
                            rbi_pick = h_df.sort_values(by='HardHit%', ascending=False).iloc[0]
                            st.error(f"**4. Pick Over RBI:** {rbi_pick['Name']} ({rbi_pick['Team']}) - *HardHit: {rbi_pick['HardHit%']}%*")
                            
                        if 'xBA' in h_df.columns:
                            hit_pick = h_df.sort_values(by='xBA', ascending=False).iloc[0]
                            sw_hit_text = f" | SweetSpot (14d): {hit_pick['SweetSpot% (14d)']}%" if 'SweetSpot% (14d)' in h_df.columns else ""
                            st.caption(f"**5. Pick Over Hit:** {hit_pick['Name']} ({hit_pick['Team']}) - *xBA: {hit_pick['xBA']}{sw_hit_text}*")

                    with col2:
                        st.markdown("### 🎯 Pitcher Picks (O/U)")
                        if 'xBA Allowed' in p_df.columns:
                            fade_hit = p_df.sort_values(by='xBA Allowed', ascending=False).iloc[0]
                            st.warning(f"**1. Target OVER Hit Allowed:**\n{fade_hit['Name']} ({fade_hit['Team']}) - *xBA Allowed: {fade_hit['xBA Allowed']}*")
                            
                        if 'xwOBA Allowed' in p_df.columns:
                            safe_out = p_df.sort_values(by='xwOBA Allowed', ascending=True).iloc[0]
                            st.success(f"**2. Target OVER Outs Recorded:**\n{safe_out['Name']} ({safe_out['Team']}) - *xwOBA Allowed: {safe_out['xwOBA Allowed']}*")
                            
                            fade_out = p_df.sort_values(by='xwOBA Allowed', ascending=False).iloc[0]
                            st.error(f"**3. Target UNDER Outs Recorded:**\n{fade_out['Name']} ({fade_out['Team']}) - *xwOBA Allowed: {fade_out['xwOBA Allowed']}*")

    # --- TAB 4: AI PREDICTIONS (MODELING GAME-BY-GAME) ---
    with tab4:
        st.subheader("🚀 AI Prop Betting Probability Model (Game-by-Game)")
        st.write("Sistem menyaring 10 pemain terbaik dari masing-masing tim (5 target HR & 5 target Hit) berdasarkan kalkulasi AI Model.")
        
        if not df_hitters.empty:
            df_h_today = df_hitters[df_hitters['Team'].isin(playing_teams)].dropna(subset=['Team'])
            
            if 'HR_Prob_Score' in df_h_today.columns:
                for game in game_details:
                    with st.expander(f"🔥 AI Prediction Modeling: {game['text']}", expanded=False):
                        col_away, col_home = st.columns(2)
                        
                        # Tim Away
                        with col_away:
                            st.markdown(f"#### 🏟️ {game['away']} (Away Team)")
                            away_df = df_h_today[df_h_today['Team'] == game['away']]
                            
                            if not away_df.empty:
                                st.write("🎯 **Top 5 HR Probability Score:**")
                                st.dataframe(away_df.sort_values('HR_Prob_Score', ascending=False).head(5)[['Name', 'HR_Prob_Score']], hide_index=True, use_container_width=True)
                                
                                st.write("🏏 **Top 5 Hit Probability Score:**")
                                st.dataframe(away_df.sort_values('Hit_Prob_Score', ascending=False).head(5)[['Name', 'Hit_Prob_Score']], hide_index=True, use_container_width=True)
                            else:
                                st.info("Data pemain away belum tersedia.")

                        # Tim Home
                        with col_home:
                            st.markdown(f"#### 🏠 {game['home']} (Home Team)")
                            home_df = df_h_today[df_h_today['Team'] == game['home']]
                            
                            if not home_df.empty:
                                st.write("🎯 **Top 5 HR Probability Score:**")
                                st.dataframe(home_df.sort_values('HR_Prob_Score', ascending=False).head(5)[['Name', 'HR_Prob_Score']], hide_index=True, use_container_width=True)
                                
                                st.write("🏏 **Top 5 Hit Probability Score:**")
                                st.dataframe(home_df.sort_values('Hit_Prob_Score', ascending=False).head(5)[['Name', 'Hit_Prob_Score']], hide_index=True, use_container_width=True)
                            else:
                                st.info("Data pemain home belum tersedia.")
            else:
                st.warning("⚠️ Kolom AI Score belum terdeteksi. Silakan jalankan 'bot_updater.py' atau tunggu jadwal update otomatis GitHub.")
