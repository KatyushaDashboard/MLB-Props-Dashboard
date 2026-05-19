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
        
        # Simpan detail penunjang analisis makro & cuaca
        game_details.append({
            'game_id': game['game_id'],
            'status': game['status'],
            'away': away_abbr, 
            'home': home_abbr, 
            'text': f"{away_abbr} @ {home_abbr}",
            'away_pitcher': game.get('away_probable_pitcher', 'Unknown Pitcher'),
            'home_pitcher': game.get('home_probable_pitcher', 'Unknown Pitcher'),
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
        temp = weather.get('temp', 'N/A')
        condition = weather.get('condition', 'N/A')
        wind = weather.get('wind', 'N/A')
        return f"{temp}°F, {condition}", wind
    except:
        return "N/A", "N/A"

# --- 3. BACA DATA CSV LOKAL ---
def load_local_data():
    try:
        df_hitters = pd.read_csv('master_hitter_2026.csv')
        df_pitchers = pd.read_csv('master_pitcher_2026.csv')
        return df_hitters, df_pitchers
    except Exception as e:
        st.error("⚠️ File CSV belum siap! Pastikan robot GitHub Actions sudah selesai memproses data Fase 1.")
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

# Tarik data awal
playing_teams, today_matchups, player_team_map, game_details = get_daily_schedule()
df_hitters, df_pitchers = load_local_data()

if not df_hitters.empty: df_hitters.insert(1, 'Team', df_hitters['Name'].map(player_team_map))
if not df_pitchers.empty: df_pitchers.insert(1, 'Team', df_pitchers['Name'].map(player_team_map))

# --- GENERATOR INTERFACE ---
if not today_matchups:
    st.warning("Tidak ada jadwal pertandingan MLB untuk hari ini.")
else:
    st.markdown("### 🏟️ Slate Summary (Pertandingan Hari Ini)")
    cols = st.columns(min(len(today_matchups), 6))
    for i, m in enumerate(today_matchups): cols[i % 6].info(m)

    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "Pitcher Matchups", 
        "Hitter Props", 
        "🔥 Daily Top Picks", 
        "🚀 AI Predictions", 
        "📡 Live Report", 
        "📈 AI Tracker",
        "🔮 SGP Builder"
    ])

    # --- TAB 1: PITCHER METRICS ---
    with tab1:
        st.subheader("Pitcher Metrics Allowed (Statcast)")
        if not df_pitchers.empty:
            df_p_today = df_pitchers[df_pitchers['Team'].isin(playing_teams)].dropna(subset=['Team'])
            allowed_metrics = [c for c in ['xwOBA Allowed', 'xSLG Allowed', 'xBA Allowed', 'HardHit% Allowed', 'Barrel% Allowed'] if c in df_p_today.columns]
            st.dataframe(df_p_today.style.background_gradient(cmap='RdYlGn', subset=allowed_metrics) if allowed_metrics else df_p_today, use_container_width=True, height=500)

    # --- TAB 2: HITTER ADVANCED & PLATOON METRICS ---
    with tab2:
        st.subheader("Hitter Advanced & Platoon Metrics")
        if not df_hitters.empty:
            df_h_today = df_hitters[df_hitters['Team'].isin(playing_teams)].dropna(subset=['Team'])
            col1, col2 = st.columns(2)
            with col1: search_name = st.text_input("🔍 Ketik Nama Pemain (Opsional):", "", key="tab2_search")
            with col2: 
                avail_teams = sorted(df_h_today['Team'].unique().tolist())
                sel_team = st.selectbox("Filter Berdasarkan Tim:", ["Semua Tim"] + avail_teams, key="tab2_select")
            
            if search_name: display_df = df_h_today[df_h_today['Name'].str.contains(search_name, case=False, na=False)]
            elif sel_team != "Semua Tim": display_df = df_h_today[df_h_today['Team'] == sel_team]
            else: display_df = df_h_today.sort_values(by='xwOBA', ascending=False).head(50)
            
            hitter_metrics = [c for c in display_df.columns if any(k in c for k in ['xwOBA', 'xBA', 'xSLG', 'HardHit', 'Barrel', 'SweetSpot'])]
            st.dataframe(display_df.style.background_gradient(cmap='RdYlGn', subset=hitter_metrics) if hitter_metrics else display_df, use_container_width=True, height=500)

    # --- TAB 3: DAILY TOP PICKS ---
    with tab3:
        st.subheader("🤖 Rekomendasi Pick Per Pertandingan")
        st.write("Daftar Pick terbaik yang diurutkan secara matematis untuk setiap pertandingan hari ini.")
        
        if not df_hitters.empty and not df_pitchers.empty:
            df_h_today = df_hitters[df_hitters['Team'].isin(playing_teams)].dropna(subset=['Team'])
            df_p_today = df_pitchers[df_pitchers['Team'].isin(playing_teams)].dropna(subset=['Team'])
            
            for game in game_details:
                with st.expander(f"⚾ Matchup: {game['away']} @ {game['home']}", expanded=False):
                    weather_cond, wind_cond = get_weather_info(game['game_id'])
                    st.markdown(f"**🏟️ {game['venue']}** | 🌤️ **Cuaca:** {weather_cond} | 💨 **Angin:** {wind_cond}")
                    st.markdown(f"⚾ **Probable Pitchers:** {game['away_pitcher']} vs {game['home_pitcher']}")
                    st.divider()
                    
                    game_teams = [game['away'], game['home']]
                    
                    # PERBAIKAN TYPO DI SINI
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
                            st.warning(f"**3. Pick Over Run:** {run_pick['Name']} ({run_pick['Team']}) - *xwOBA: {run_pick['xwOBA']}*")
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

    # --- TAB 4: AI PROBABILITY MODEL & PLATOON SPLITS ---
    with tab4:
        st.subheader("🚀 AI Prop Probability Model & Platoon Splits")
        if not df_hitters.empty:
            df_h_today = df_hitters[df_hitters['Team'].isin(playing_teams)].dropna(subset=['Team'])
            if 'HR_Prob_Score' in df_h_today.columns:
                for game in game_details:
                    with st.expander(f"🔥 AI Prediction: {game['text']}", expanded=False):
                        weather_cond, wind_cond = get_weather_info(game['game_id'])
                        st.markdown(f"**🏟️ {game['venue']}** | 🌤️ **Cuaca:** {weather_cond} | 💨 **Angin:** {wind_cond}")
                        st.markdown(f"⚾ **Probable Pitchers:** {game['away_pitcher']} vs {game['home_pitcher']}")
                        st.divider()

                        col_away, col_home = st.columns(2)
                        with col_away:
                            st.markdown(f"#### 🏟️ {game['away']} (vs Starter {game['home_pitcher']})")
                            away_df = df_h_today[df_h_today['Team'] == game['away']]
                            if not away_df.empty:
                                hr_cols = ['Name', 'HR_Prob_Score'] + [c for c in ['xwOBA_vs_L', 'xwOBA_vs_R'] if c in away_df.columns]
                                hit_cols = ['Name', 'Hit_Prob_Score'] + [c for c in ['xBA_vs_L', 'xBA_vs_R'] if c in away_df.columns]
                                st.write("🎯 **Top 5 HR Index & Platoon:**")
                                st.dataframe(away_df.sort_values('HR_Prob_Score', ascending=False).head(5)[hr_cols], hide_index=True, use_container_width=True)
                                st.write("🏏 **Top 5 Hit Index & Platoon:**")
                                st.dataframe(away_df.sort_values('Hit_Prob_Score', ascending=False).head(5)[hit_cols], hide_index=True, use_container_width=True)

                        with col_home:
                            st.markdown(f"#### 🏠 {game['home']} (vs Starter {game['away_pitcher']})")
                            home_df = df_h_today[df_h_today['Team'] == game['home']]
                            if not home_df.empty:
                                hr_cols = ['Name', 'HR_Prob_Score'] + [c for c in ['xwOBA_vs_L', 'xwOBA_vs_R'] if c in home_df.columns]
                                hit_cols = ['Name', 'Hit_Prob_Score'] + [c for c in ['xBA_vs_L', 'xBA_vs_R'] if c in home_df.columns]
                                st.write("🎯 **Top 5 HR Index & Platoon:**")
                                st.dataframe(home_df.sort_values('HR_Prob_Score', ascending=False).head(5)[hr_cols], hide_index=True, use_container_width=True)
                                st.write("🏏 **Top 5 Hit Index & Platoon:**")
                                st.dataframe(home_df.sort_values('Hit_Prob_Score', ascending=False).head(5)[hit_cols], hide_index=True, use_container_width=True)
            else:
                st.warning("⚠️ Menunggu data Platoon CSV selesai di-generate oleh robot GitHub.")

    # --- TAB 5: LIVE REPORT ---
    with tab5:
        st.subheader("📡 Live Report & Hasil Pemain Hari Ini")
        for game in game_details:
            if game['status'] in ['Scheduled', 'Pre-Game', 'Warmup']:
                with st.expander(f"⏳ {game['away']} @ {game['home']}", expanded=False): st.info("Pertandingan belum dimulai.")
                continue
            with st.expander(f"🔥 {game['away']} @ {game['home']} - {game['status']}", expanded=False):
                live_h, live_p = get_live_boxscore(game['game_id'], game['away'], game['home'])
                if not live_h.empty and not live_p.empty:
                    sukses_h = live_h[(live_h['H'] >= 1) | (live_h['HR'] >= 1) | (live_h['R'] >= 1) | (live_h['RBI'] >= 1) | (live_h['TB'] >= 1)]
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("### 🏏 Hitters (Pencetak Skor)")
                        if not sukses_h.empty: st.dataframe(sukses_h.sort_values(by=['TB', 'H'], ascending=False), hide_index=True, use_container_width=True)
                        else: st.write("Belum ada hitter yang mencetak angka.")
                    with c2:
                        st.markdown("### 🎯 Pitchers (Rapor Lemparan)")
                        st.dataframe(live_p[['Team', 'Name', 'IP', 'H Allowed', 'R Allowed', 'SO']], hide_index=True, use_container_width=True)
                else: st.write("Sedang menyinkronkan data boxscore...")

    # --- TAB 6: ACCURACY TRACKER ---
    with tab6:
        st.subheader("📈 AI Model Accuracy & Slip Tracker (22 Picks Per Game)")
        if not df_hitters.empty:
            df_h_today = df_hitters[df_hitters['Team'].isin(playing_teams)].dropna(subset=['Team'])
            for game in game_details:
                if game['status'] in ['Scheduled', 'Pre-Game', 'Warmup']:
                    with st.expander(f"⏳ Tracker: {game['away']} @ {game['home']}", expanded=False): st.info("Menunggu pertandingan dimulai...")
                    continue
                with st.expander(f"📊 Slip Verification: {game['away']} @ {game['home']}", expanded=False):
                    live_h, _ = get_live_boxscore(game['game_id'], game['away'], game['home'])
                    h_df = df_h_today[df_h_today['Team'].isin([game['away'], game['home']])]
                    
                    if not live_h.empty and not h_df.empty and 'HR_Prob_Score' in h_df.columns:
                        targets = []
                        if 'Barrel%' in h_df.columns:
                            tb = h_df.sort_values('Barrel%', ascending=False).iloc[0]
                            targets.append({'name': tb['Name'], 'team': tb['Team'], 'prop': '⭐ Tab 3 - Top HR (Barrel%)'})
                        if 'xBA' in h_df.columns:
                            tx = h_df.sort_values('xBA', ascending=False).iloc[0]
                            targets.append({'name': tx['Name'], 'team': tx['Team'], 'prop': '⭐ Tab 3 - Top Hit (xBA)'})
                        
                        for team_abbr, loc in [(game['away'], 'Away'), (game['home'], 'Home')]:
                            team_df = h_df[h_df['Team'] == team_abbr]
                            if not team_df.empty:
                                for _, r in team_df.sort_values('HR_Prob_Score', ascending=False).head(5).iterrows():
                                    targets.append({'name': r['Name'], 'team': r['Team'], 'prop': f'🔥 Tab 4 - {loc} Top 5 HR Index'})
                                for _, r in team_df.sort_values('Hit_Prob_Score', ascending=False).head(5).iterrows():
                                    targets.append({'name': r['Name'], 'team': r['Team'], 'prop': f'🏏 Tab 4 - {loc} Top 5 Hit Index'})
                                    
                        v_rows = []
                        for t in targets:
                            p_live = live_h[live_h['Name'] == t['name']]
                            if not p_live.empty:
                                act_h, act_hr = int(p_live.iloc[0]['H']), int(p_live.iloc[0]['HR'])
                                status = "✅ WIN (BOOM HR!)" if 'HR' in t['prop'] and act_hr >= 1 else ("✅ WIN (HIT SUCCESS)" if 'Hit' in t['prop'] and act_h >= 1 else ("⏳ LIVE" if game['status'] != 'Final' else "❌ MISS"))
                                field_res = f"Hit: {act_h} | HR: {act_hr}"
                            else:
                                status, field_res = ("⏳ Belum Batting" if game['status'] != 'Final' else "❌ MISS (DNP)"), "Hit: 0 | HR: 0"
                            v_rows.append({'Tim': t['team'], 'Nama Pemain': t['name'], 'Kategori Taruhan': t['prop'], 'Hasil Riil': field_res, 'Status Slip': status})
                        st.dataframe(pd.DataFrame(v_rows), hide_index=True, use_container_width=True)

    # --- TAB 7: CRYSTAL BALL SGP & GAME PROPS BUILDER ---
    with tab7:
        st.subheader("🔮 AI Game Props & Same Game Parlay (SGP) Builder")
        st.write("Modul ini mengagregasi performa pemukul melawan tipe pelempar hari ini untuk memproyeksikan target pasar.")
        
        if not game_details:
            st.info("Tidak ada pertandingan yang tersedia untuk pembuatan SGP.")
        elif not df_hitters.empty and not df_pitchers.empty:
            game_options = [g['text'] for g in game_details]
            selected_match = st.selectbox("🎯 Pilih Pertandingan untuk Racikan SGP:", game_options, key="sgp_select")
            
            g_sel = next(g for g in game_details if g['text'] == selected_match)
            w_cond, wind_cond = get_weather_info(g_sel['game_id'])
            st.info(f"🏟️ Stadion: {g_sel['venue']} | 🌤️ Cuaca: {w_cond} | 💨 Angin: {wind_cond}")
            
            st.markdown("### 📊 Proyeksi Pasar Tim & Total Match")
            c_makro1, c_makro2 = st.columns(2)
            
            h_away_df = df_hitters[df_hitters['Team'] == g_sel['away']]
            h_home_df = df_hitters[df_hitters['Team'] == g_sel['home']]
            
            with c_makro1:
                st.markdown(f"#### 🏟️ Proyeksi {g_sel['away']}")
                avg_xwoba_away = h_away_df['xwOBA_vs_R'].mean() if not h_away_df.empty else 0.310
                avg_xslg_away = h_away_df['xSLG'].mean() if not h_away_df.empty else 0.410
                proj_runs_away = round((avg_xwoba_away * 12) + (avg_xslg_away * 2), 1)
                st.write(f"📈 Proyeksi Team Runs: **{proj_runs_away} Runs**")
                st.write(f"🎯 Rekomendasi: **OVER {round(proj_runs_away - 0.5)}.5 Team Runs**" if avg_xwoba_away >= 0.320 else f"📉 Target: **UNDER {round(proj_runs_away + 0.5)}.5 Team Runs**")
                
            with c_makro2:
                st.markdown(f"#### 🏠 Proyeksi {g_sel['home']}")
                avg_xwoba_home = h_home_df['xwOBA_vs_R'].mean() if not h_home_df.empty else 0.315
                avg_xslg_home = h_home_df['xSLG'].mean() if not h_home_df.empty else 0.420
                proj_runs_home = round((avg_xwoba_home * 12) + (avg_xslg_home * 2), 1)
                st.write(f"📈 Proyeksi Team Runs: **{proj_runs_home} Runs**")
                st.write(f"🎯 Rekomendasi: **OVER {round(proj_runs_home - 0.5)}.5 Team Runs**" if avg_xwoba_home >= 0.320 else f"📉 Target: **UNDER {round(proj_runs_home + 0.5)}.5 Team Runs**")
            
            st.divider()
            st.markdown("### ⚡ AI Automated Same Game Parlay Builder")
            st.write("Sistem menyaring 3 pemukul dengan indikator lampu hijau terbanyak.")
            
            match_hitters = pd.concat([h_away_df, h_home_df])
            if not match_hitters.empty:
                def get_light_indicator(xwoba_val):
                    if xwoba_val >= 0.360: return "🟢 (Elite Target)"
                    elif xwoba_val >= 0.300: return "🟡 (Solid Bet)"
                    else: return "🔴 (High Risk)"
                
                if 'xwOBA_vs_L' in match_hitters.columns and 'xwOBA_vs_R' in match_hitters.columns:
                    match_hitters['Status_LHP'] = match_hitters['xwOBA_vs_L'].apply(get_light_indicator)
                    match_hitters['Status_RHP'] = match_hitters['xwOBA_vs_R'].apply(get_light_indicator)
                    
                    green_players = match_hitters[(match_hitters['xwOBA_vs_R'] >= 0.340) | (match_hitters['xwOBA_vs_L'] >= 0.340)].head(3)
                    
                    if not green_players.empty:
                        st.success("🔥 **REKOMENDASI KOMBINASI SLIP SGP (HIGH CONFIDENCE):**")
                        for idx, row in green_players.iterrows():
                            chosen_score = row['xwOBA_vs_R'] if row['xwOBA_vs_R'] >= row['xwOBA_vs_L'] else row['xwOBA_vs_L']
                            st.markdown(f"**Leg:** {row['Name']} ({row['Team']}) ➔ **OVER 0.5 HIT** — *Split xwOBA: {chosen_score}* 🟢")
                    else:
                        st.warning("🟡 Tidak ada pemukul dengan kriteria indikator hijau malam ini. Hindari SGP.")
                else:
                    st.warning("⚠️ Data Platoon belum tersedia. Jalankan bot updater terlebih dahulu.")
