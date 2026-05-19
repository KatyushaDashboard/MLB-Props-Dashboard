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

# --- 2. TARIK JADWAL & PROBABLE PITCHERS (DENGAN L/R TRACKER) ---
@st.cache_data(ttl=1800)
def get_daily_schedule():
    games = statsapi.schedule(date=mlb_date_str)
    playing_teams = []
    today_matchups = []
    player_to_team = {}
    game_details = []
    
    # Fungsi pencari tangan pelempar otomatis
    def get_hand(name):
        if name in ['Unknown Pitcher', 'Unknown', 'TBD']: return "-"
        try:
            res = statsapi.lookup_player(name)
            if res: return res[0].get('pitchHand', {}).get('code', '-')
        except: pass
        return "-"
    
    for game in games:
        away_abbr = team_mapper.get(game['away_name'], game['away_name'])
        home_abbr = team_mapper.get(game['home_name'], game['home_name'])
        
        playing_teams.extend([away_abbr, home_abbr])
        matchup_text = f"{away_abbr} @ {home_abbr} ({game.get('game_datetime', '')[11:16]} ET) - {game['status']}"
        today_matchups.append(matchup_text)
        
        away_p = game.get('away_probable_pitcher', 'Unknown Pitcher')
        home_p = game.get('home_probable_pitcher', 'Unknown Pitcher')
        
        game_details.append({
            'game_id': game['game_id'],
            'status': game['status'],
            'away': away_abbr, 
            'home': home_abbr, 
            'text': f"{away_abbr} @ {home_abbr}",
            'away_pitcher': away_p,
            'home_pitcher': home_p,
            'away_hand': get_hand(away_p),
            'home_hand': get_hand(home_p),
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
        game_data = statsapi.get('game', {'gamePk': game_id}).get('gameData', {})
        weather = game_data.get('weather', {})
        if not weather: return "TBD (Belum Update / Dome)", "TBD"
        
        temp = weather.get('temp', 'TBD')
        condition = weather.get('condition', 'TBD')
        wind = weather.get('wind', 'TBD')
        return f"{temp}°F, {condition}", wind
    except: return "N/A", "N/A"

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
    except: return pd.DataFrame(), pd.DataFrame()

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
            st.dataframe(df_p_today.style.background_gradient(cmap='RdYlGn', subset=allowed_metrics) if allowed_metrics else df_p_today, use_container_width=True, height=500)

    with tab2:
        st.subheader("Hitter Advanced & Platoon Metrics")
        if not df_hitters.empty:
            df_h_today = df_hitters[df_hitters['Team'].isin(playing_teams)].dropna(subset=['Team'])
            col1, col2 = st.columns(2)
            with col1: search_name = st.text_input("🔍 Ketik Nama Pemain:", "")
            with col2: sel_team = st.selectbox("Filter Tim:", ["Semua Tim"] + sorted(df_h_today['Team'].unique().tolist()))
            
            display_df = df_h_today[df_h_today['Name'].str.contains(search_name, case=False, na=False)] if search_name else (df_h_today[df_h_today['Team'] == sel_team] if sel_team != "Semua Tim" else df_h_today.sort_values(by='xwOBA', ascending=False).head(50))
            metrics = [c for c in display_df.columns if any(k in c for k in ['xwOBA', 'xBA', 'xSLG', 'HardHit'])]
            st.dataframe(display_df.style.background_gradient(cmap='RdYlGn', subset=metrics) if metrics else display_df, use_container_width=True, height=500)

    # --- TAB 3: DAILY TOP PICKS (DENGAN BOX DESAIN BARU) ---
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
                            if 'Barrel%' in h_df.columns:
                                top_hr = h_df.sort_values(by='Barrel%', ascending=False).iloc[0]
                                st.success(f"**1. Over HR:** {top_hr['Name']} ({top_hr['Team']})\n\n↳ *Alasan: Barrel tertinggi di {top_hr['Barrel%']}%*")
                            if 'Max EV' in h_df.columns:
                                top_ev = h_df.sort_values(by='Max EV', ascending=False).iloc[0]
                                st.success(f"**↳ Dark Horse HR:** {top_ev['Name']}\n\n↳ *Alasan: Pukulan terkeras tercatat di {top_ev['Max EV']} mph*")
                            if 'xSLG' in h_df.columns:
                                top_xslg = h_df.sort_values(by='xSLG', ascending=False).iloc[0]
                                st.info(f"**2. Over Total Base:** {top_xslg['Name']} ({top_xslg['Team']})\n\n↳ *Alasan: xSLG memimpin di {top_xslg['xSLG']}*")
                            if 'xwOBA' in h_df.columns:
                                top_xwoba = h_df.sort_values(by='xwOBA', ascending=False).iloc[0]
                                st.warning(f"**3. Over Run:** {top_xwoba['Name']} ({top_xwoba['Team']})\n\n↳ *Alasan: Konsistensi xwOBA di angka {top_xwoba['xwOBA']}*")
                            if 'HardHit%' in h_df.columns:
                                top_hh = h_df.sort_values(by='HardHit%', ascending=False).iloc[0]
                                st.error(f"**4. Over RBI:** {top_hh['Name']} ({top_hh['Team']})\n\n↳ *Alasan: Daya HardHit mencapai {top_hh['HardHit%']}%*")
                            if 'xBA' in h_df.columns:
                                top_xba = h_df.sort_values(by='xBA', ascending=False).iloc[0]
                                st.success(f"**5. Over Hit:** {top_xba['Name']} ({top_xba['Team']})\n\n↳ *Alasan: xBA tertinggi (Raja Kontak) di {top_xba['xBA']}*")

                    with col2:
                        st.markdown("### 🎯 Probable Pitchers (O/U)")
                        for p_name, p_team in [(game['away_pitcher'], game['away']), (game['home_pitcher'], game['home'])]:
                            if p_name != 'Unknown Pitcher':
                                last_name = p_name.split()[-1]
                                p_match = df_p_today[(df_p_today['Team'] == p_team) & (df_p_today['Name'].str.contains(last_name, case=False, na=False))]
                                
                                if not p_match.empty:
                                    p_stat = p_match.iloc[0]
                                    xba_alwd = p_stat.get('xBA Allowed', 0.250)
                                    xwoba_alwd = p_stat.get('xwOBA Allowed', 0.320)
                                    
                                    hit_rec = "OVER Hit Allowed" if xba_alwd >= 0.250 else "UNDER Hit Allowed"
                                    out_rec = "UNDER Outs Recorded" if xwoba_alwd >= 0.330 else "OVER Outs Recorded"
                                    
                                    st.info(f"⚾ **{p_stat['Name']}** ({p_team})\n\n"
                                            f"↳ **Target 1: {hit_rec}** *(xBA Allowed: {xba_alwd})*\n\n"
                                            f"↳ **Target 2: {out_rec}** *(xwOBA Allowed: {xwoba_alwd})*")
                                else:
                                    st.write(f"⚾ **{p_name}** ({p_team}) - *Metrik Statcast belum cukup*")

    # --- TAB 4: AI PROBABILITY MODEL (DENGAN LABEL PITCHER L/R) ---
    with tab4:
        st.subheader("🚀 AI Prop Probability Model")
        if not df_hitters.empty:
            df_h_today = df_hitters[df_hitters['Team'].isin(playing_teams)].dropna(subset=['Team'])
            if 'HR_Prob_Score' in df_h_today.columns:
                for game in game_details:
                    with st.expander(f"🔥 AI Prediction: {game['text']}", expanded=False):
                        w_cond, wind_cond = get_weather_info(game['game_id'])
                        st.markdown(f"**🏟️ {game['venue']}** | 🌤️ {w_cond} | 💨 {wind_cond}")
                        
                        # INJEKSI LABEL TANGAN L/R DI SINI
                        away_p_disp = f"{game['away_pitcher']} ({game['away_hand']})" if game['away_pitcher'] != 'Unknown Pitcher' else "Unknown Pitcher"
                        home_p_disp = f"{game['home_pitcher']} ({game['home_hand']})" if game['home_pitcher'] != 'Unknown Pitcher' else "Unknown Pitcher"
                        
                        st.markdown(f"⚾ **Probable Pitchers:** {away_p_disp} vs {home_p_disp}")
                        st.divider()

                        col_away, col_home = st.columns(2)
                        with col_away:
                            st.markdown(f"#### 🏟️ {game['away']} (vs {home_p_disp})")
                            away_df = df_h_today[df_h_today['Team'] == game['away']]
                            if not away_df.empty:
                                hr_cols = ['Name', 'HR_Prob_Score'] + [c for c in ['xwOBA_vs_L', 'xwOBA_vs_R'] if c in away_df.columns]
                                hit_cols = ['Name', 'Hit_Prob_Score'] + [c for c in ['xBA_vs_L', 'xBA_vs_R'] if c in away_df.columns]
                                st.write("🎯 **Top 5 HR Index & Platoon:**")
                                st.dataframe(away_df.sort_values('HR_Prob_Score', ascending=False).head(5)[hr_cols], hide_index=True, use_container_width=True)
                                st.write("🏏 **Top 5 Hit Index & Platoon:**")
                                st.dataframe(away_df.sort_values('Hit_Prob_Score', ascending=False).head(5)[hit_cols], hide_index=True, use_container_width=True)

                        with col_home:
                            st.markdown(f"#### 🏠 {game['home']} (vs {away_p_disp})")
                            home_df = df_h_today[df_h_today['Team'] == game['home']]
                            if not home_df.empty:
                                hr_cols = ['Name', 'HR_Prob_Score'] + [c for c in ['xwOBA_vs_L', 'xwOBA_vs_R'] if c in home_df.columns]
                                hit_cols = ['Name', 'Hit_Prob_Score'] + [c for c in ['xBA_vs_L', 'xBA_vs_R'] if c in home_df.columns]
                                st.write("🎯 **Top 5 HR Index & Platoon:**")
                                st.dataframe(home_df.sort_values('HR_Prob_Score', ascending=False).head(5)[hr_cols], hide_index=True, use_container_width=True)
                                st.write("🏏 **Top 5 Hit Index & Platoon:**")
                                st.dataframe(home_df.sort_values('Hit_Prob_Score', ascending=False).head(5)[hit_cols], hide_index=True, use_container_width=True)

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
        st.subheader("📈 AI Model Accuracy Tracker (22 Picks Per Game)")
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
                st.markdown("#### 💣 OPSI 1: 3-Leg HR Parlay (High Risk / High Reward)")
                hr_pool = m_hitters.sort_values('HR_Prob_Score', ascending=False).head(3)
                for _, r in hr_pool.iterrows():
                    st.write(f"- 🎯 **{r['Name']}** ({r['Team']}) ➔ **OVER 0.5 Home Run** *(AI Score: {r['HR_Prob_Score']})*")
                
                st.markdown("#### 🏏 OPSI 2: 4-Leg Total Base Parlay (Solid Bet)")
                tb_pool = m_hitters.sort_values('xSLG', ascending=False).head(4)
                for _, r in tb_pool.iterrows():
                    st.write(f"- ⚾ **{r['Name']}** ({r['Team']}) ➔ **OVER 1.5 Total Bases** *(xSLG: {r['xSLG']})*")
                
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
                add_mix_leg(m_hitters.sort_values('Hit_Prob_Score', ascending=False), "OVER 0.5 Hit", "Hit_Prob_Score")
                
                for leg in mix_legs: st.write(leg)
            else:
                st.warning("⚠️ Data AI Model belum lengkap untuk membuat SGP.")
