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

# --- 3. BACA DATA LOKAL ---
@st.cache_data
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

    tab1, tab2, tab3 = st.tabs(["Pitcher Matchups (Allowed)", "Hitter Props", "🔥 Game-by-Game Top Picks"])

    with tab1:
        st.subheader("Pitcher Metrics Allowed")
        if not df_pitchers.empty:
            df_p_today = df_pitchers[df_pitchers['Team'].isin(playing_teams)].dropna(subset=['Team'])
            allowed_cols = [c for c in ['xwOBA Allowed', 'xSLG Allowed', 'xBA Allowed', 'HardHit% Allowed', 'Barrel% Allowed'] if c in df_p_today.columns]
            st.dataframe(df_p_today.style.background_gradient(cmap='RdYlGn', subset=allowed_cols), use_container_width=True, height=400)

    with tab2:
        st.subheader("Hitter Advanced Metrics")
        if not df_hitters.empty:
            df_h_today = df_hitters[df_hitters['Team'].isin(playing_teams)].dropna(subset=['Team'])
            # Tampilkan SEMUA metrik 14 hari yang berhasil terunduh
            hit_cols = [c for c in ['xwOBA', 'xSLG', 'xBA', 'HardHit%', 'Barrel%', 'Max EV', 'SweetSpot% (14d)', 'HardHit% (14d)', 'Barrel% (14d)', 'xwOBA (14d)'] if c in df_h_today.columns]
            st.dataframe(df_h_today.style.background_gradient(cmap='RdYlGn', subset=hit_cols), use_container_width=True, height=400)

    with tab3:
        st.subheader("🤖 Rekomendasi Pick Per Pertandingan")
        
        if not df_hitters.empty and not df_pitchers.empty:
            df_h_today = df_hitters[df_hitters['Team'].isin(playing_teams)].dropna(subset=['Team'])
            df_p_today = df_pitchers[df_pitchers['Team'].isin(playing_teams)].dropna(subset=['Team'])
            
            for game in game_details:
                with st.expander(f"⚾ Matchup: {game['text']}", expanded=False):
                    h_df = df_h_today[df_h_today['Team'].isin([game['away'], game['home']])]
                    p_df = df_p_today[df_p_today['Team'].isin([game['away'], game['home']])]
                    
                    if h_df.empty or p_df.empty: continue
                        
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("### 🏏 Hitter Picks")
                        
                        # 1. Over HR
                        if 'Barrel%' in h_df.columns:
                            hr_pick = h_df.sort_values(by='Barrel%', ascending=False).iloc[0]
                            st.success(f"**1. Main Pick HR:** {hr_pick['Name']} ({hr_pick['Team']})\n*Barrel: {hr_pick['Barrel%']}%*")
                        if 'Max EV' in h_df.columns:
                            dark_hr = h_df.sort_values(by='Max EV', ascending=False).iloc[0]
                            st.success(f"**↳ Dark Horse HR (Max EV):** {dark_hr['Name']} ({dark_hr['Team']})\n*Pukulan Terkeras: {dark_hr['Max EV']} mph*")
                        
                        # 2. Over Total Base (Berdasarkan xSLG Saja agar selalu muncul!)
                        if 'xSLG' in h_df.columns:
                            tb_pick = h_df.sort_values(by='xSLG', ascending=False).iloc[0]
                            sw_text = f" | SweetSpot (14d): {tb_pick['SweetSpot% (14d)']}%" if 'SweetSpot% (14d)' in h_df.columns else ""
                            st.info(f"**2. Pick Over Total Base:** {tb_pick['Name']} ({tb_pick['Team']})\n*xSLG: {tb_pick['xSLG']}{sw_text}*")
                            
                        # 3. Over Run (xwOBA)
                        if 'xwOBA' in h_df.columns:
                            run_pick = h_df.sort_values(by='xwOBA', ascending=False).iloc[0]
                            st.warning(f"**3. Pick Over Run:** {run_pick['Name']} ({run_pick['Team']})\n*xwOBA: {run_pick['xwOBA']}*")

                        # 4. Over RBI (HardHit%)
                        if 'HardHit%' in h_df.columns:
                            rbi_pick = h_df.sort_values(by='HardHit%', ascending=False).iloc[0]
                            st.error(f"**4. Pick Over RBI:** {rbi_pick['Name']} ({rbi_pick['Team']})\n*HardHit: {rbi_pick['HardHit%']}%*")
                            
                        # 5. Over Hit (Berdasarkan xBA Saja agar selalu muncul!)
                        if 'xBA' in h_df.columns:
                            hit_pick = h_df.sort_values(by='xBA', ascending=False).iloc[0]
                            sw_hit_text = f" | SweetSpot (14d): {hit_pick['SweetSpot% (14d)']}%" if 'SweetSpot% (14d)' in h_df.columns else ""
                            st.success(f"**5. Pick Over Hit:** {hit_pick['Name']} ({hit_pick['Team']})\n*xBA: {hit_pick['xBA']}{sw_hit_text}*")

                    with col2:
                        st.markdown("### 🎯 Pitcher Picks (O/U)")
                        if 'xBA Allowed' in p_df.columns:
                            fade_hit = p_df.sort_values(by='xBA Allowed', ascending=False).iloc[0]
                            st.warning(f"**1. Target OVER Hit Allowed:**\n{fade_hit['Name']} ({fade_hit['Team']})\n*xBA Allowed: {fade_hit['xBA Allowed']}*")
                            
                        if 'xwOBA Allowed' in p_df.columns:
                            safe_out = p_df.sort_values(by='xwOBA Allowed', ascending=True).iloc[0]
                            st.success(f"**2. Target OVER Outs Recorded:**\n{safe_out['Name']} ({safe_out['Team']})\n*Paling aman, xwOBA Allowed: {safe_out['xwOBA Allowed']}*")
                            
                            fade_out = p_df.sort_values(by='xwOBA Allowed', ascending=False).iloc[0]
                            st.error(f"**3. Target UNDER Outs Recorded:**\n{fade_out['Name']} ({fade_out['Team']})\n*Rawan bocor, xwOBA Allowed: {fade_out['xwOBA Allowed']}*")