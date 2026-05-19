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
        matchup_text = f"{away_abbr} @ {home_abbr} ({game.get('game_datetime', '')[11:16]} ET) - {game['status']}"
        today_matchups.append(matchup_text)
        
        # Menyimpan ID Game & Status untuk kebutuhan Tab 5 (Live Report)
        game_details.append({
            'game_id': game['game_id'],
            'status': game['status'],
            'away': away_abbr, 
            'home': home_abbr, 
            'text': matchup_text
        })
        
        try:
            for p in statsapi.get('team_roster', {'teamId': game['away_id']})['roster']:
                player_to_team[p['person']['fullName']] = away_abbr
            for p in statsapi.get('team_roster', {'teamId': game['home_id']})['roster']:
                player_to_team[p['person']['fullName']] = home_abbr
        except: continue
    return playing_teams, today_matchups, player_to_team, game_details

def load_local_data():
    try:
        df_hitters = pd.read_csv('master_hitter_2026.csv')
        df_pitchers = pd.read_csv('master_pitcher_2026.csv')
        return df_hitters, df_pitchers
    except Exception as e:
        st.error("⚠️ File CSV belum ada! Jalankan 'python bot_updater.py' di CMD terlebih dahulu.")
        return pd.DataFrame(), pd.DataFrame()

# FUNGSI BARU KHUSUS TAB 5: Tarik data Boxscore Live (Di-cache 5 menit biar cepat)
@st.cache_data(ttl=300)
def get_live_boxscore(game_id, away_abbr, home_abbr):
    try:
        box = statsapi.boxscore_data(game_id)
        hitters, pitchers = [], []
        
        for side, abbr in [('away', away_abbr), ('home', home_abbr)]:
            players = box.get(side, {}).get('players', {})
            for pid, pdata in players.items():
                name = pdata.get('person', {}).get('fullName', 'Unknown')
                b_stats = pdata.get('stats', {}).get('batting', {})
                p_stats = pdata.get('stats', {}).get('pitching', {})
                
                # Ekstrak Hitter (Hanya yang sudah memukul)
                if b_stats and b_stats.get('plateAppearances', 0) > 0:
                    hitters.append({
                        'Team': abbr, 'Name': name,
                        'AB': b_stats.get('atBats', 0), 'R': b_stats.get('runs', 0),
                        'H': b_stats.get('hits', 0), 'HR': b_stats.get('homeRuns', 0),
                        'RBI': b_stats.get('rbi', 0), 
                        'TB': b_stats.get('totalBases', b_stats.get('hits',0)) # Fallback if missing
                    })
                
                # Ekstrak Pitcher (Hanya yang sudah melempar)
                if p_stats and p_stats.get('battersFaced', 0) > 0:
                    ip = str(p_stats.get('inningsPitched', '0.0'))
                    parts = ip.split('.')
                    outs = int(parts[0]) * 3
                    if len(parts) > 1: outs += int(parts[1])
                    
                    pitchers.append({
                        'Team': abbr, 'Name': name, 'IP': ip, 'Outs': outs,
                        'H Allowed': p_stats.get('hits', 0), 'R Allowed': p_stats.get('runs', 0),
                        'SO': p_stats.get('strikeOuts', 0)
                    })
                    
        return pd.DataFrame(hitters), pd.DataFrame(pitchers)
    except:
        return pd.DataFrame(), pd.DataFrame()


playing_teams, today_matchups, player_team_map, game_details = get_daily_schedule()
df_hitters, df_pitchers = load_local_data()

if not df_hitters.empty:
    df_hitters.insert(1, 'Team', df_hitters['Name'].map(player_team_map))
if not df_pitchers.empty:
    df_pitchers.insert(1, 'Team', df_pitchers['Name'].map(player_team_map))

if not today_matchups:
    st.warning("Tidak ada jadwal pertandingan MLB untuk hari ini.")
else:
    st.markdown("### 🏟️ Slate Summary (Pertandingan Hari Ini)")
    cols = st.columns(min(len(today_matchups), 6))
    for i, m in enumerate(today_matchups): cols[i % 6].info(m)

    # 5 TABS UTAMA SEKARANG
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Pitcher Matchups", 
        "Hitter Props", 
        "🔥 Daily Top Picks",
        "🚀 AI Predictions",
        "📡 Live Report & Results"
    ])

    with tab1:
        st.subheader("Pitcher Metrics Allowed")
        if not df_pitchers.empty:
            df_p_today = df_pitchers[df_pitchers['Team'].isin(playing_teams)].dropna(subset=['Team'])
            styled_pitchers = df_p_today.style
            allowed_metrics = [c for c in ['xwOBA Allowed', 'xSLG Allowed', 'xBA Allowed', 'HardHit% Allowed', 'Barrel% Allowed'] if c in df_p_today.columns]
            if allowed_metrics: styled_pitchers = styled_pitchers.background_gradient(cmap='RdYlGn', subset=allowed_metrics)
            st.dataframe(styled_pitchers, use_container_width=True, height=500)

    with tab2:
        st.subheader("Hitter Advanced & Expected Metrics")
        if not df_hitters.empty:
            df_h_today = df_hitters[df_hitters['Team'].isin(playing_teams)].dropna(subset=['Team'])
            col1, col2 = st.columns(2)
            with col1: search_name = st.text_input("🔍 Ketik Nama Pemain (Opsional):", "")
            with col2: 
                available_teams = sorted(df_h_today['Team'].unique().tolist())
                selected_team = st.selectbox("Atau Filter Berdasarkan Tim:", ["Semua Tim"] + available_teams)
            
            if search_name: display_df = df_h_today[df_h_today['Name'].str.contains(search_name, case=False, na=False)]
            elif selected_team != "Semua Tim": display_df = df_h_today[df_h_today['Team'] == selected_team]
            else:
                sort_col = 'xwOBA (14d)' if 'xwOBA (14d)' in df_h_today.columns else ('xwOBA' if 'xwOBA' in df_h_today.columns else df_h_today.columns[2])
                display_df = df_h_today.sort_values(by=sort_col, ascending=False).head(50)
            
            styled_hitters = display_df.style
            hitter_metrics = [c for c in ['xwOBA', 'xSLG', 'xBA', 'HardHit%', 'Barrel%', 'Max EV', 'SweetSpot% (14d)', 'HardHit% (14d)', 'Barrel% (14d)', 'xwOBA (14d)'] if c in display_df.columns]
            if hitter_metrics: styled_hitters = styled_hitters.background_gradient(cmap='RdYlGn', subset=hitter_metrics)
            st.dataframe(styled_hitters, use_container_width=True, height=500)

    with tab3:
        st.subheader("🤖 Rekomendasi Pick Per Pertandingan")
        if not df_hitters.empty and not df_pitchers.empty:
            df_h_today = df_hitters[df_hitters['Team'].isin(playing_teams)].dropna(subset=['Team'])
            df_p_today = df_pitchers[df_pitchers['Team'].isin(playing_teams)].dropna(subset=['Team'])
            for game in game_details:
                with st.expander(f"⚾ Matchup: {game['text']}", expanded=False):
                    game_teams = [game['away'], game['home']]
                    h_df = df_h_today[df_h_today['Team'].isin(game_teams)]
                    p_df = df_p_today[df_p_today['Team'].isin(game_teams)]
                    if h_df.empty or p_df.empty: continue
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"### 🏏 Hitter Picks ({game['away']} & {game['home']})")
                        if 'Barrel%' in h_df.columns:
                            hr_pick = h_df.sort_values(by='Barrel%', ascending=False).iloc[0]
                            st.success(f"**1. Over HR:** {hr_pick['Name']} ({hr_pick['Team']})")
                        if 'Max EV' in h_df.columns:
                            dark_hr = h_df.sort_values(by='Max EV', ascending=False).iloc[0]
                            st.success(f"**↳ Dark Horse HR:** {dark_hr['Name']} ({dark_hr['Team']})")
                        if 'xSLG' in h_df.columns:
                            tb_pick = h_df.sort_values(by='xSLG', ascending=False).iloc[0]
                            st.info(f"**2. Over Total Base:** {tb_pick['Name']} ({tb_pick['Team']})")
                        if 'xwOBA' in h_df.columns:
                            run_pick = h_df.sort_values(by='xwOBA', ascending=False).iloc[0]
                            st.warning(f"**3. Over Run:** {run_pick['Name']} ({run_pick['Team']})")
                        if 'HardHit%' in h_df.columns:
                            rbi_pick = h_df.sort_values(by='HardHit%', ascending=False).iloc[0]
                            st.error(f"**4. Over RBI:** {rbi_pick['Name']} ({rbi_pick['Team']})")
                        if 'xBA' in h_df.columns:
                            hit_pick = h_df.sort_values(by='xBA', ascending=False).iloc[0]
                            st.caption(f"**5. Over Hit:** {hit_pick['Name']} ({hit_pick['Team']})")

                    with col2:
                        st.markdown("### 🎯 Pitcher Picks (O/U)")
                        if 'xBA Allowed' in p_df.columns:
                            fade_hit = p_df.sort_values(by='xBA Allowed', ascending=False).iloc[0]
                            st.warning(f"**1. OVER Hit Allowed:** {fade_hit['Name']} ({fade_hit['Team']})")
                        if 'xwOBA Allowed' in p_df.columns:
                            safe_out = p_df.sort_values(by='xwOBA Allowed', ascending=True).iloc[0]
                            st.success(f"**2. OVER Outs Recorded:** {safe_out['Name']} ({safe_out['Team']})")
                            fade_out = p_df.sort_values(by='xwOBA Allowed', ascending=False).iloc[0]
                            st.error(f"**3. UNDER Outs Recorded:** {fade_out['Name']} ({fade_out['Team']})")

    with tab4:
        st.subheader("🚀 AI Prop Betting Probability Model (Game-by-Game)")
        if not df_hitters.empty:
            df_h_today = df_hitters[df_hitters['Team'].isin(playing_teams)].dropna(subset=['Team'])
            if 'HR_Prob_Score' in df_h_today.columns:
                for game in game_details:
                    with st.expander(f"🔥 AI Prediction Modeling: {game['text']}", expanded=False):
                        col_away, col_home = st.columns(2)
                        with col_away:
                            st.markdown(f"#### 🏟️ {game['away']} (Away Team)")
                            away_df = df_h_today[df_h_today['Team'] == game['away']]
                            if not away_df.empty:
                                st.write("🎯 **Top 5 HR Probability Score:**")
                                st.dataframe(away_df.sort_values('HR_Prob_Score', ascending=False).head(5)[['Name', 'HR_Prob_Score']], hide_index=True, use_container_width=True)
                                st.write("🏏 **Top 5 Hit Probability Score:**")
                                st.dataframe(away_df.sort_values('Hit_Prob_Score', ascending=False).head(5)[['Name', 'Hit_Prob_Score']], hide_index=True, use_container_width=True)
                        with col_home:
                            st.markdown(f"#### 🏠 {game['home']} (Home Team)")
                            home_df = df_h_today[df_h_today['Team'] == game['home']]
                            if not home_df.empty:
                                st.write("🎯 **Top 5 HR Probability Score:**")
                                st.dataframe(home_df.sort_values('HR_Prob_Score', ascending=False).head(5)[['Name', 'HR_Prob_Score']], hide_index=True, use_container_width=True)
                                st.write("🏏 **Top 5 Hit Probability Score:**")
                                st.dataframe(home_df.sort_values('Hit_Prob_Score', ascending=False).head(5)[['Name', 'Hit_Prob_Score']], hide_index=True, use_container_width=True)
            else:
                st.warning("⚠️ Kolom AI Score belum terdeteksi. Silakan jalankan 'bot_updater.py' atau tunggu jadwal update otomatis GitHub.")

    # --- TAB 5: LIVE REPORT BARU ---
    with tab5:
        st.subheader("📡 Live Report & Hasil Pemain Hari Ini")
        st.write("Cek langsung performa pemainmu di sini. Data ditarik *real-time* dari MLB dan menyaring pemain yang berhasil mencetak skor.")
        
        for game in game_details:
            # Jika game belum main, lewati tarikan boxscore
            if game['status'] in ['Scheduled', 'Pre-Game', 'Warmup']:
                with st.expander(f"⏳ {game['text']}", expanded=False):
                    st.info("Pertandingan belum dimulai.")
                continue
                
            # Jika game Live atau Final
            with st.expander(f"🔥 {game['text']}", expanded=False):
                live_h, live_p = get_live_boxscore(game['game_id'], game['away'], game['home'])
                
                if not live_h.empty and not live_p.empty:
                    # Filter Hitter: Hanya tampilkan pemain yang mencetak minimal 1 (H/HR/R/RBI/TB)
                    sukses_h = live_h[(live_h['H'] >= 1) | (live_h['HR'] >= 1) | (live_h['R'] >= 1) | (live_h['RBI'] >= 1) | (live_h['TB'] >= 1)]
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("### 🏏 Hitters (Pencetak Skor)")
                        if not sukses_h.empty:
                            st.dataframe(sukses_h.sort_values(by=['TB', 'H'], ascending=False), hide_index=True, use_container_width=True)
                        else:
                            st.write("Belum ada hitter yang mencetak angka.")
                            
                    with c2:
                        st.markdown("### 🎯 Pitchers (Rapor Lemparan)")
                        st.dataframe(live_p[['Team', 'Name', 'IP', 'Outs', 'H Allowed', 'R Allowed', 'SO']], hide_index=True, use_container_width=True)
                else:
                    st.write("Sedang mengambil data / Data belum masuk ke server MLB.")
