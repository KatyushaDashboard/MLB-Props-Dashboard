import streamlit as st
import pandas as pd
import statsapi
import pytz
from datetime import datetime

st.set_page_config(page_title="MLB AI Props Dashboard", layout="wide")
st.title("⚾ MLB Daily Matchup & AI Predictions")

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

@st.cache_data
def load_local_data():
    try:
        df_hitters = pd.read_csv('master_hitter_2026.csv')
        df_pitchers = pd.read_csv('master_pitcher_2026.csv')
        return df_hitters, df_pitchers
    except:
        st.error("⚠️ Data belum siap. Pastikan robot GitHub Actions sudah berjalan.")
        return pd.DataFrame(), pd.DataFrame()

playing_teams, today_matchups, player_team_map, game_details = get_daily_schedule()
df_hitters, df_pitchers = load_local_data()

if not df_hitters.empty:
    df_hitters.insert(1, 'Team', df_hitters['Name'].map(player_team_map))
if not df_pitchers.empty:
    df_pitchers.insert(1, 'Team', df_pitchers['Name'].map(player_team_map))

if not today_matchups:
    st.warning("Tidak ada jadwal pertandingan hari ini.")
else:
    # --- DEFENISI 4 TAB UTAMA ---
    tab1, tab2, tab3, tab4 = st.tabs([
        "Pitcher Matchups (Allowed)", 
        "Hitter Props (Full Stats)", 
        "Daily Top Picks (Metrics)", 
        "🚀 AI Probability Predictions"
    ])

    with tab1:
        st.subheader("Pitcher Metrics Allowed")
        if not df_pitchers.empty:
            df_p_today = df_pitchers[df_pitchers['Team'].isin(playing_teams)].dropna(subset=['Team'])
            st.dataframe(df_p_today.style.background_gradient(cmap='RdYlGn'), use_container_width=True)

    with tab2:
        st.subheader("Hitter Advanced & Expected Metrics")
        if not df_hitters.empty:
            df_h_today = df_hitters[df_hitters['Team'].isin(playing_teams)].dropna(subset=['Team'])
            st.dataframe(df_h_today.style.background_gradient(cmap='RdYlGn'), use_container_width=True)

    with tab3:
        st.subheader("🤖 Metric-Based Leaders per Game")
        if not df_hitters.empty:
            df_h_today = df_hitters[df_hitters['Team'].isin(playing_teams)].dropna(subset=['Team'])
            for game in game_details:
                with st.expander(f"Matchup: {game['text']}"):
                    h_df = df_h_today[df_h_today['Team'].isin([game['away'], game['home']])]
                    if not h_df.empty:
                        col1, col2, col3 = st.columns(3)
                        try:
                            col1.metric("Top Barrel% (HR Target)", h_df.sort_values('Barrel%', ascending=False).iloc[0]['Name'])
                            col2.metric("Top xBA (Hit Target)", h_df.sort_values('xBA', ascending=False).iloc[0]['Name'])
                            col3.metric("Top xSLG (TB Target)", h_df.sort_values('xSLG', ascending=False).iloc[0]['Name'])
                        except:
                            st.write("Data tidak lengkap untuk matchup ini.")

    with tab4:
        st.subheader("🚀 AI Prop Betting Probability Model (Game-by-Game)")
        st.write("Sistem menyaring 10 pemain terbaik dari masing-masing tim (5 target HR & 5 target Hit) berdasarkan kalkulasi AI Model.")
        
        if not df_hitters.empty:
            df_h_today = df_hitters[df_hitters['Team'].isin(playing_teams)].dropna(subset=['Team'])
            
            # Cek validasi apakah kolom skor AI sudah digenerate oleh robot
            if 'HR_Prob_Score' in df_h_today.columns:
                for game in game_details:
                    with st.expander(f"🔥 AI Prediction Modeling: {game['text']}"):
                        col_away, col_home = st.columns(2)
                        
                        # --- TIM AWAY (Tamu) ---
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

                        # --- TIM HOME (Tuan Rumah) ---
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
