import streamlit as st
import pandas as pd
import statsapi
import pytz
from datetime import datetime

st.set_page_config(page_title="MLB AI Props Dashboard", layout="wide")
st.title("⚾ MLB Daily Matchup, AI Predictions & SGP Builder")

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

# --- 2. TARIK JADWAL & PROBABLE PITCHERS ---
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
        
        game_details.append({
            'game_id': game['game_id'],
            'status': game['status'],
            'away': away_abbr, 
            'home': home_abbr, 
            'text': f"{away_abbr} @ {home_abbr}",
            'away_pitcher': game.get('away_probable_pitcher', 'Unknown'),
            'home_pitcher': game.get('home_probable_pitcher', 'Unknown'),
            'venue': game.get('venue_name', 'Unknown Stadium')
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
        return f"{weather.get('temp', 'N/A')}°F, {weather.get('condition', 'N/A')}", weather.get('wind', 'N/A')
    except:
        return "N/A", "N/A"

# --- 3. BACA DATA CSV LOKAL ---
def load_local_data():
    try:
        df_h = pd.read_csv('master_hitter_2026.csv')
        df_p = pd.read_csv('master_pitcher_2026.csv')
        return df_h, df_p
    except Exception as e:
        st.error("⚠️ File CSV belum siap! Pastikan robot GitHub Actions sudah selesai.")
        return pd.DataFrame(), pd.DataFrame()

# --- 4. LIVE REPORT BOXSCORE DATA ---
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
                    hitters.append({'Team': abbr, 'Name': name, 'AB': b_stats.get('atBats', 0), 'H': b_stats.get('hits', 0), 'HR': b_stats.get('homeRuns', 0), 'TB': b_stats.get('totalBases', b_stats.get('hits', 0))})
                if p_stats and p_stats.get('battersFaced', 0) > 0:
                    pitchers.append({'Team': abbr, 'Name': name, 'IP': str(p_stats.get('inningsPitched', '0.0')), 'H Allowed': p_stats.get('hits', 0), 'SO': p_stats.get('strikeOuts', 0)})
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

    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "Pitcher Matchups", "Hitter Props", "🔥 Daily Top Picks", 
        "🚀 AI Predictions", "📡 Live Report", "📈 AI Tracker", "🔮 SGP Builder"
    ])

    with tab1:
        st.subheader("Pitcher Metrics Allowed")
        if not df_pitchers.empty:
            df_p_today = df_pitchers[df_pitchers['Team'].isin(playing_teams)].dropna(subset=['Team'])
            allowed_metrics = [c for c in ['xwOBA Allowed', 'xSLG Allowed', 'xBA Allowed'] if c in df_p_today.columns]
            st.dataframe(df_p_today.style.background_gradient(cmap='RdYlGn', subset=allowed_metrics) if allowed_metrics else df_p_today, use_container_width=True)

    with tab2:
        st.subheader("Hitter Advanced & Platoon Metrics")
        if not df_hitters.empty:
            df_h_today = df_hitters[df_hitters['Team'].isin(playing_teams)].dropna(subset=['Team'])
            col1, col2 = st.columns(2)
            with col1: search_name = st.text_input("🔍 Ketik Nama Pemain:", "")
            with col2: sel_team = st.selectbox("Filter Tim:", ["Semua Tim"] + sorted(df_h_today['Team'].unique().tolist()))
            
            display_df = df_h_today[df_h_today['Name'].str.contains(search_name, case=False, na=False)] if search_name else (df_h_today[df_h_today['Team'] == sel_team] if sel_team != "Semua Tim" else df_h_today.sort_values(by='xwOBA', ascending=False).head(50))
            metrics = [c for c in display_df.columns if any(k in c for k in ['xwOBA', 'xBA', 'xSLG', 'HardHit'])]
            st.dataframe(display_df.style.background_gradient(cmap='RdYlGn', subset=metrics) if metrics else display_df, use_container_width=True)

    # --- TAB 3: DAILY TOP PICKS (NEW PITCHER LOGIC) ---
    with tab3:
        st.subheader("🤖 Rekomendasi Pick Per Pertandingan")
        if not df_hitters.empty and not df_pitchers.empty:
            df_h_today = df_hitters[df_hitters['Team'].isin(playing_teams)].dropna(subset=['Team'])
            df_p_today = df_pitchers[df_pitchers['Team'].isin(playing_teams)].dropna(subset=['Team'])
            
            for game in game_details:
                with st.expander(f"⚾ Matchup: {game['away']} @ {game['home']}", expanded=False):
                    w_cond, wind_cond = get_weather_info(game['game_id'])
                    st.markdown(f"**🏟️ {game['venue']}** | 🌤️ {w_cond} | 💨 {wind_cond}")
                    st.divider()
                    
                    game_teams = [game['away'], game['home']]
                    h_df = df_h_today[df_h_today['Team'].isin(game_teams)]
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown(f"### 🏏 Hitter Picks")
                        if not h_df.empty:
                            if 'Barrel%' in h_df.columns: st.success(f"**1. Over HR:** {h_df.sort_values(by='Barrel%', ascending=False).iloc[0]['Name']} ({h_df.sort_values(by='Barrel%', ascending=False).iloc[0]['Team']})")
                            if 'Max EV' in h_df.columns: st.success(f"**↳ Dark Horse HR:** {h_df.sort_values(by='Max EV', ascending=False).iloc[0]['Name']}")
                            if 'xSLG' in h_df.columns: st.info(f"**2. Over Total Base:** {h_df.sort_values(by='xSLG', ascending=False).iloc[0]['Name']}")
                            if 'xwOBA' in h_df.columns: st.warning(f"**3. Over Run:** {h_df.sort_values(by='xwOBA', ascending=False).iloc[0]['Name']}")
                            if 'HardHit%' in h_df.columns: st.error(f"**4. Over RBI:** {h_df.sort_values(by='HardHit%', ascending=False).iloc[0]['Name']}")
                            if 'xBA' in h_df.columns: st.caption(f"**5. Over Hit:** {h_df.sort_values(by='xBA', ascending=False).iloc[0]['Name']}")

                    with col2:
                        st.markdown("### 🎯 Probable Pitchers (O/U)")
                        away_p, home_p = game['away_pitcher'], game['home_pitcher']
                        
                        for p_name, p_team in [(away_p, game['away']), (home_p, game['home'])]:
                            if p_name != 'Unknown':
                                last_name = p_name.split()[-1]
                                p_match = df_p_today[(df_p_today['Team'] == p_team) & (df_p_today['Name'].str.contains(last_name, case=False, na=False))]
                                
                                if not p_match.empty:
                                    p_stat = p_match.iloc[0]
                                    xba_alwd = p_stat.get('xBA Allowed', 0.250)
                                    xwoba_alwd = p_stat.get('xwOBA Allowed', 0.320)
                                    
                                    hit_rec = "OVER Hit Allowed" if xba_alwd >= 0.250 else "UNDER Hit Allowed"
                                    out_rec = "UNDER Outs Recorded" if xwoba_alwd >= 0.330 else "OVER Outs Recorded"
                                    
                                    st.write(f"⚾ **{p_stat['Name']}** ({p_team})")
                                    st.caption(f"↳ Target 1: **{hit_rec}** (xBA: {xba_alwd})")
                                    st.caption(f"↳ Target 2: **{out_rec}** (xwOBA: {xwoba_alwd})")
                                    st.write("---")
                                else:
                                    st.write(f"⚾ **{p_name}** ({p_team}) - *Metrik Statcast belum cukup*")

    with tab4:
        st.subheader("🚀 AI Prop Probability Model")
        if not df_hitters.empty:
            df_h_today = df_hitters[df_hitters['Team'].isin(playing_teams)].dropna(subset=['Team'])
            if 'HR_Prob_Score' in df_h_today.columns:
                for game in game_details:
                    with st.expander(f"🔥 AI Prediction: {game['text']}", expanded=False):
                        col_a, col_b = st.columns(2)
                        with col_a:
                            df_away = df_h_today[df_h_today['Team'] == game['away']]
                            if not df_away.empty: st.dataframe(df_away.sort_values('HR_Prob_Score', ascending=False).head(5)[['Name', 'HR_Prob_Score', 'xwOBA_vs_R', 'xwOBA_vs_L']], hide_index=True)
                        with col_b:
                            df_home = df_h_today[df_h_today['Team'] == game['home']]
                            if not df_home.empty: st.dataframe(df_home.sort_values('HR_Prob_Score', ascending=False).head(5)[['Name', 'HR_Prob_Score', 'xwOBA_vs_R', 'xwOBA_vs_L']], hide_index=True)

    with tab5:
        st.subheader("📡 Live Report & Hasil Pemain")
        for game in game_details:
            if game['status'] not in ['Scheduled', 'Pre-Game']:
                with st.expander(f"🔥 {game['text']} - {game['status']}", expanded=False):
                    l_h, _ = get_live_boxscore(game['game_id'], game['away'], game['home'])
                    if not l_h.empty: st.dataframe(l_h[(l_h['H'] >= 1) | (l_h['HR'] >= 1)], hide_index=True, use_container_width=True)

    with tab6:
        st.subheader("📈 AI Model Accuracy Tracker")
        st.write("Verifikasi otomatis masih berjalan di *background*...")

    # --- TAB 7: THE ULTIMATE SGP BUILDER ---
    with tab7:
        st.subheader("🔮 AI Game Props & SGP Builder")
        if not game_details:
            st.info("Tidak ada pertandingan yang tersedia.")
        elif not df_hitters.empty:
            game_opts = [g['text'] for g in game_details]
            sel_match = st.selectbox("🎯 Pilih Pertandingan:", game_opts)
            g_sel = next(g for g in game_details if g['text'] == sel_match)
            
            h_away = df_hitters[df_hitters['Team'] == g_sel['away']]
            h_home = df_hitters[df_hitters['Team'] == g_sel['home']]
            
            st.markdown("### 📊 Proyeksi Pasar Tim & Total Match")
            c_mak1, c_mak2 = st.columns(2)
            
            with c_mak1:
                st.markdown(f"#### 🏟️ {g_sel['away']} (Away)")
                xba_a, xslg_a = (h_away['xBA'].mean(), h_away['xSLG'].mean()) if not h_away.empty else (0.240, 0.400)
                proj_r_a = round((h_away['xwOBA_vs_R'].mean() * 12) + (xslg_a * 2), 1) if not h_away.empty else 4.0
                st.write(f"📈 Proyeksi Team Runs: **{proj_r_a}**")
                st.caption(f"🏏 Proyeksi Singles: **{round(xba_a * 25, 1)}** | Doubles: **{round(xslg_a * 4.5, 1)}**")
                
            with c_mak2:
                st.markdown(f"#### 🏠 {g_sel['home']} (Home)")
                xba_h, xslg_h = (h_home['xBA'].mean(), h_home['xSLG'].mean()) if not h_home.empty else (0.240, 0.400)
                proj_r_h = round((h_home['xwOBA_vs_R'].mean() * 12) + (xslg_h * 2), 1) if not h_home.empty else 4.0
                st.write(f"📈 Proyeksi Team Runs: **{proj_r_h}**")
                st.caption(f"🏏 Proyeksi Singles: **{round(xba_h * 25, 1)}** | Doubles: **{round(xslg_h * 4.5, 1)}**")
            
            st.divider()
            st.markdown("### ⚡ AI Automated SGP Builder (3 Opsi Strategi)")
            m_hitters = pd.concat([h_away, h_home])
            
            if not m_hitters.empty and 'HR_Prob_Score' in m_hitters.columns:
                # Opsi 1: 3-Leg HR (High Risk)
                st.markdown("#### 💣 OPSI 1: 3-Leg HR Parlay (High Risk / High Reward)")
                hr_pool = m_hitters.sort_values('HR_Prob_Score', ascending=False).head(3)
                for _, r in hr_pool.iterrows():
                    st.write(f"- 🎯 **{r['Name']}** ({r['Team']}) ➔ **OVER 0.5 Home Run** *(AI Score: {r['HR_Prob_Score']})*")
                
                # Opsi 2: 4-Leg Total Base (Solid)
                st.markdown("#### 🏏 OPSI 2: 4-Leg Total Base Parlay (Solid Bet)")
                tb_pool = m_hitters.sort_values('xSLG', ascending=False).head(4)
                for _, r in tb_pool.iterrows():
                    st.write(f"- ⚾ **{r['Name']}** ({r['Team']}) ➔ **OVER 1.5 Total Bases** *(xSLG: {r['xSLG']})*")
                
                # Opsi 3: 5-Leg Campuran Terseleksi
                st.markdown("#### 🥗 OPSI 3: 5-Leg Mix Parlay (Hit, Run, RBI, TB)")
                used_names = set()
                mix_legs = []
                
                def add_mix_leg(df_sorted, prop_text, metric_col):
                    for _, r in df_sorted.iterrows():
                        if r['Name'] not in used_names:
                            used_names.add(r['Name'])
                            mix_legs.append(f"- ✅ **{r['Name']}** ({r['Team']}) ➔ **{prop_text}** *({metric_col}: {r[metric_col]})*")
                            break
                            
                add_mix_leg(m_hitters.sort_values('xBA', ascending=False), "OVER 0.5 Hit", "xBA")
                add_mix_leg(m_hitters.sort_values('xSLG', ascending=False), "OVER 1.5 Total Base", "xSLG")
                add_mix_leg(m_hitters.sort_values('xwOBA', ascending=False), "OVER 0.5 Run", "xwOBA")
                add_mix_leg(m_hitters.sort_values('HardHit%', ascending=False), "OVER 0.5 RBI", "HardHit%")
                add_mix_leg(m_hitters.sort_values('Hit_Prob_Score', ascending=False), "OVER 0.5 Hit", "Hit Score")
                
                for leg in mix_legs: st.write(leg)
            else:
                st.warning("⚠️ Data AI Model belum lengkap untuk membuat SGP.")
