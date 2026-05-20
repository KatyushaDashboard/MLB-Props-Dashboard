import streamlit as st
import pandas as pd
import statsapi
import pytz
from datetime import datetime

st.set_page_config(page_title="MLB AI Props Dashboard", layout="wide")
st.title("⚾ MLB Daily Matchup, AI Predictions & Parlay Command Center")

# --- 1. ZONA WAKTU & TIME MACHINE ---
wib_tz = pytz.timezone('Asia/Jakarta')
now_est = datetime.now(wib_tz).astimezone(pytz.timezone('US/Eastern')).date()

st.sidebar.header("⚙️ Kontrol Jendela Kerja")
selected_date = st.sidebar.date_input("📅 Pilih Tanggal Laga (US Time):", now_est)
mlb_date_str = selected_date.strftime('%m/%d/%Y')

st.write(f"📅 **Menampilkan Data Untuk Tanggal (US Time):** {mlb_date_str}")

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

fallback_bullpen_era = {
    "NYY": 3.40, "LAD": 3.55, "BAL": 3.80, "ATL": 3.65, "HOU": 3.90,
    "PHI": 3.45, "SEA": 3.25, "MIL": 3.70, "CLE": 3.15, "SDP": 3.60
}

# --- 2. TARIK JADWAL & PROBABLE PITCHERS ---
@st.cache_data(ttl=86400)
def get_pitcher_hand(name):
    if not name or str(name).strip() == "" or name in ['Unknown Pitcher', 'Unknown', 'TBD']: return "-"
    try:
        res = statsapi.lookup_player(name)
        if not res: return "-"
        pid = res[0]['id']
        p_data = statsapi.get('person', {'personId': pid})
        hand = p_data.get('people', [{}])[0].get('pitchHand', {}).get('code', '-')
        return hand
    except:
        return "-"

@st.cache_data(ttl=1800)
def get_daily_schedule(target_date):
    games = statsapi.schedule(date=target_date)
    playing_teams, today_matchups, player_to_team, game_details = [], [], {}, []
    
    for game in games:
        away_abbr = team_mapper.get(game['away_name'], game['away_name'])
        home_abbr = team_mapper.get(game['home_name'], game['home_name'])
        playing_teams.extend([away_abbr, home_abbr])
        matchup_text = f"{away_abbr} @ {home_abbr} ({game.get('game_datetime', '')[11:16]} ET)"
        today_matchups.append(matchup_text)
        
        away_p = game.get('away_probable_pitcher', 'Unknown Pitcher')
        home_p = game.get('home_probable_pitcher', 'Unknown Pitcher')
        
        game_details.append({
            'game_id': game['game_id'], 'status': game['status'], 'away': away_abbr, 'home': home_abbr, 
            'text': f"{away_abbr} @ {home_abbr}", 'away_pitcher': away_p, 'home_pitcher': home_p,
            'away_hand': get_pitcher_hand(away_p), 'home_hand': get_pitcher_hand(home_p),
            'venue': game.get('venue_name', 'Unknown Stadium')
        })
        try:
            for p in statsapi.get('team_roster', {'teamId': game['away_id']})['roster']: player_to_team[p['person']['fullName']] = away_abbr
            for p in statsapi.get('team_roster', {'teamId': game['home_id']})['roster']: player_to_team[p['person']['fullName']] = home_abbr
        except: continue
    return playing_teams, today_matchups, player_to_team, game_details

@st.cache_data(ttl=3600)
def get_weather_info(game_id):
    try:
        w = statsapi.get('game', {'gamePk': game_id}).get('gameData', {}).get('weather', {})
        if not w: return "TBD (Belum Update / Dome)", "TBD"
        return f"{w.get('temp', 'TBD')}°F, {w.get('condition', 'TBD')}", w.get('wind', 'TBD')
    except: return "N/A", "N/A"

# --- 3. BACA DATA CSV LOKAL ---
def load_local_data():
    try:
        return pd.read_csv('master_hitter_2026.csv'), pd.read_csv('master_pitcher_2026.csv')
    except:
        st.error("⚠️ File CSV belum siap! Pastikan skrip pembuat CSV lokal sudah berjalan.")
        return pd.DataFrame(), pd.DataFrame()

# --- 4. LIVE BOXSCORE ---
@st.cache_data(ttl=300)
def get_live_boxscore(game_id, away_abbr, home_abbr):
    try:
        raw = statsapi.get('game_boxscore', {'gamePk': game_id})
        teams_data = raw.get('teams', {})
        hitters, pitchers = [], []
        for side, abbr in [('away', away_abbr), ('home', home_abbr)]:
            players = teams_data.get(side, {}).get('players', {})
            for pid, pdata in players.items():
                name = pdata.get('person', {}).get('fullName', 'Unknown')
                b, p = pdata.get('stats', {}).get('batting', {}), pdata.get('stats', {}).get('pitching', {})
                if b and b.get('plateAppearances', 0) > 0:
                    hitters.append({'Team': abbr, 'Name': name, 'AB': b.get('atBats', 0), 'R': b.get('runs', 0), 'H': b.get('hits', 0), 'HR': b.get('homeRuns', 0), 'RBI': b.get('rbi', 0), 'TB': b.get('totalBases', b.get('hits', 0))})
                if p and p.get('battersFaced', 0) > 0:
                    pitchers.append({'Team': abbr, 'Name': name, 'IP': str(p.get('inningsPitched', '0.0')), 'H Allowed': p.get('hits', 0), 'R Allowed': p.get('runs', 0), 'SO': p.get('strikeOuts', 0)})
        return pd.DataFrame(hitters), pd.DataFrame(pitchers)
    except: return pd.DataFrame(), pd.DataFrame()

playing_teams, today_matchups, player_team_map, game_details = get_daily_schedule(mlb_date_str)
df_hitters, df_pitchers = load_local_data()

# Penjaga kolom duplikat Team
if not df_hitters.empty and 'Team' not in df_hitters.columns: 
    df_hitters.insert(1, 'Team', df_hitters['Name'].map(player_team_map))
if not df_pitchers.empty and 'Team' not in df_pitchers.columns: 
    df_pitchers.insert(1, 'Team', df_pitchers['Name'].map(player_team_map))

# --- UI MAIN CONTAINER ---
if not today_matchups:
    st.warning("Tidak ada jadwal pertandingan MLB pada tanggal ini.")
else:
    st.markdown("### 🏟️ Slate Summary")
    cols = st.columns(min(len(today_matchups), 6))
    for i, m in enumerate(today_matchups): cols[i % 6].info(m)

    tabs = st.tabs([
        "Pitcher Matchups", "Hitter Props", "🔥 Daily Top Picks", 
        "🚀 AI Predictions", "📡 Live / Final Report", "📈 AI Tracker", 
        "🔮 SGP Builder", "🌍 Cross-Game Parlay", "🎯 FINAL SLIPS"
    ])

    with tabs[0]:
        st.subheader("Pitcher Metrics & Team Bullpen ERA Allowed")
        if not df_pitchers.empty:
            df_p_today = df_pitchers[df_pitchers['Team'].isin(playing_teams)].dropna(subset=['Team']).copy()
            if 'Bullpen_ERA' not in df_p_today.columns:
                df_p_today['Bullpen_ERA'] = df_p_today['Team'].map(fallback_bullpen_era).fillna(4.15)
            allowed_metrics = [c for c in ['xwOBA Allowed', 'xSLG Allowed', 'xBA Allowed', 'Bullpen_ERA'] if c in df_p_today.columns]
            st.dataframe(df_p_today.style.background_gradient(cmap='RdYlGn_r', subset=['Bullpen_ERA']) if 'Bullpen_ERA' in df_p_today.columns else df_p_today, use_container_width=True, height=500)

    with tabs[1]:
        st.subheader("Hitter Advanced, Batting Order & Recent Form (14d)")
        if not df_hitters.empty:
            df_h_today = df_hitters[df_hitters['Team'].isin(playing_teams)].dropna(subset=['Team']).copy()
            if 'Batting_Order' not in df_h_today.columns: df_h_today['Batting_Order'] = 3
            if 'PA_L14' not in df_h_today.columns: df_h_today['PA_L14'] = 45
            if 'xwOBA_L14' not in df_h_today.columns: df_h_today['xwOBA_L14'] = df_h_today['xwOBA']
            
            col1, col2 = st.columns(2)
            with col1: search_name = st.text_input("🔍 Ketik Nama Pemain:", "", key="tab2_s")
            with col2: sel_team = st.selectbox("Filter Tim:", ["Semua Tim"] + sorted(df_h_today['Team'].unique().tolist()), key="tab2_t")
            
            display_df = df_h_today[df_h_today['Name'].str.contains(search_name, case=False, na=False)] if search_name else (df_h_today[df_h_today['Team'] == sel_team] if sel_team != "Semua Tim" else df_h_today.sort_values(by='xwOBA_L14', ascending=False).head(50))
            st.dataframe(display_df, use_container_width=True, height=500)

    # --- TAB 3: RESTORED FULL 6 PICKS ---
    with tabs[2]:
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
                        for p_name, p_team, p_hand in [(game['away_pitcher'], game['away'], game['away_hand']), (game['home_pitcher'], game['home'], game['home_hand'])]:
                            if p_name and isinstance(p_name, str) and p_name.strip() and p_name not in ['Unknown Pitcher', 'Unknown', 'TBD']:
                                last_name = p_name.split()[-1]
                                p_match = df_p_today[(df_p_today['Team'] == p_team) & (df_p_today['Name'].str.contains(last_name, case=False, na=False))]
                                if not p_match.empty:
                                    p_stat = p_match.iloc[0]
                                    
                                    # Tarik data dari CSV
                                    xba_alwd = p_stat.get('xBA Allowed', 0.250)
                                    xwoba_alwd = p_stat.get('xwOBA Allowed', 0.320)
                                    k_9 = p_stat.get('K/9', 8.0)
                                    k_pct = p_stat.get('K%', 20.0)
                                    
                                    # Logika Mesin AI untuk O/U Pitcher
                                    hit_rec = "OVER Hit Allowed" if xba_alwd >= 0.250 else "UNDER Hit Allowed"
                                    out_rec = "UNDER Outs Recorded" if xwoba_alwd >= 0.330 else "OVER Outs Recorded"
                                    
                                    if k_9 >= 9.5 or k_pct >= 25.0:
                                        so_rec = "🔥 OVER Strikeouts (Raja K)"
                                    elif k_9 <= 7.5 or k_pct <= 18.0:
                                        so_rec = "🧊 UNDER Strikeouts (Pitcher Kontak)"
                                    else:
                                        so_rec = "⚖️ NO BET Strikeouts (Rata-rata)"
                                        
                                    st.info(f"⚾ **{p_stat['Name']}** ({p_team} - {p_hand})\n\n↳ **Target 1: {so_rec}** *(K/9: {k_9} | K%: {k_pct}%)*\n\n↳ **Target 2: {hit_rec}** *(xBA Allowed: {xba_alwd})*\n\n↳ **Target 3: {out_rec}** *(xwOBA Allowed: {xwoba_alwd})*")
                                else: st.write(f"⚾ **{p_name}** ({p_team} - {p_hand}) - *Metrik Statcast belum cukup*")
                            else: st.write(f"⚾ **Pitcher Belum Ditentukan** ({p_team})")

    # --- TAB 4: RESTORED FULL DUAL TABLES ---
    with tabs[3]:
        st.subheader("🚀 AI Prop Probability Model")
        if not df_hitters.empty:
            df_h_today = df_hitters[df_hitters['Team'].isin(playing_teams)].dropna(subset=['Team'])
            if 'HR_Prob_Score' in df_h_today.columns:
                for game in game_details:
                    with st.expander(f"🔥 AI Prediction: {game['text']}", expanded=False):
                        w_cond, wind_cond = get_weather_info(game['game_id'])
                        st.markdown(f"**🏟️ {game['venue']}** | 🌤️ {w_cond} | 💨 {wind_cond}")
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

    with tabs[4]:
        st.subheader("📡 Live Report & Final Boxscore")
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

    with tabs[5]:
        st.subheader("📈 AI Model Accuracy Tracker")
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
                        if 'Barrel%' in h_df.columns: targets.append({'name': h_df.sort_values('Barrel%', ascending=False).iloc[0]['Name'], 'team': h_df.sort_values('Barrel%', ascending=False).iloc[0]['Team'], 'prop': '⭐ Tab 3 - Top HR (Barrel%)'})
                        if 'xBA' in h_df.columns: targets.append({'name': h_df.sort_values('xBA', ascending=False).iloc[0]['Name'], 'team': h_df.sort_values('xBA', ascending=False).iloc[0]['Team'], 'prop': '⭐ Tab 3 - Top Hit (xBA)'})
                        for team_abbr, loc in [(game['away'], 'Away'), (game['home'], 'Home')]:
                            team_df = h_df[h_df['Team'] == team_abbr]
                            if not team_df.empty:
                                for _, r in team_df.sort_values('HR_Prob_Score', ascending=False).head(5).iterrows(): targets.append({'name': r['Name'], 'team': r['Team'], 'prop': f'🔥 Tab 4 - {loc} Top 5 HR Index'})
                                for _, r in team_df.sort_values('Hit_Prob_Score', ascending=False).head(5).iterrows(): targets.append({'name': r['Name'], 'team': r['Team'], 'prop': f'🏏 Tab 4 - {loc} Top 5 Hit Index'})
                        v_rows = []
                        for t in targets:
                            p_live = live_h[live_h['Name'] == t['name']]
                            if not p_live.empty:
                                act_h, act_hr = int(p_live.iloc[0]['H']), int(p_live.iloc[0]['HR'])
                                status = "✅ WIN (BOOM HR!)" if 'HR' in t['prop'] and act_hr >= 1 else ("✅ WIN (HIT SUCCESS)" if 'Hit' in t['prop'] and act_h >= 1 else ("⏳ LIVE" if game['status'] != 'Final' else "❌ MISS"))
                                field_res = f"Hit: {act_h} | HR: {act_hr}"
                            else: status, field_res = ("⏳ Belum Batting" if game['status'] != 'Final' else "❌ MISS (DNP)"), "Hit: 0 | HR: 0"
                            v_rows.append({'Tim': t['team'], 'Nama Pemain': t['name'], 'Kategori Taruhan': t['prop'], 'Hasil Riil': field_res, 'Status Slip': status})
                        st.dataframe(pd.DataFrame(v_rows), hide_index=True, use_container_width=True)

    # --- TAB 7: RESTORED FULL SGP BUILDER ---
    with tabs[6]:
        st.subheader("🔮 AI Game Props & Same Game Parlay (SGP) Builder")
        if not game_details:
            st.info("Tidak ada pertandingan yang tersedia.")
        elif not df_hitters.empty and not df_pitchers.empty:
            game_opts = [g['text'] for g in game_details]
            sel_match = st.selectbox("🎯 Pilih Pertandingan untuk Racikan SGP:", game_opts, key="tab7_match_select")
            g_sel = next(g for g in game_details if g['text'] == sel_match)
            
            h_away = df_hitters[df_hitters['Team'] == g_sel['away']]
            h_home = df_hitters[df_hitters['Team'] == g_sel['home']]
            
            b_era_away = fallback_bullpen_era.get(g_sel['away'], 4.15)
            b_era_home = fallback_bullpen_era.get(g_sel['home'], 4.15)
            
            st.markdown("### 📊 Proyeksi Pasar Tim & Analisis Bullpen")
            c_mak1, c_mak2 = st.columns(2)
            with c_mak1:
                st.markdown(f"#### 🏟️ {g_sel['away']} (Away)")
                xba_a, xslg_a = (h_away['xBA'].mean(), h_away['xSLG'].mean()) if not h_away.empty else (0.240, 0.400)
                
                # Injeksi Pengaruh Bullpen Lawan (b_era_home) ke Proyeksi Away
                bp_mod_a = b_era_home / 4.00 
                proj_r_a = round(((h_away['xwOBA_vs_R'].mean() * 12) + (xslg_a * 2)) * bp_mod_a, 1) if not h_away.empty else round(4.0 * bp_mod_a, 1)
                
                st.write(f"📈 Proyeksi Team Runs: **{proj_r_a}**")
                st.caption(f"🏏 Proyeksi Singles: **{round((xba_a * 25) * bp_mod_a, 1)}** | Doubles: **{round((xslg_a * 4.5) * bp_mod_a, 1)}**")
                st.write(f"🛡️ **Team Bullpen ERA:** {b_era_away}")
            with c_mak2:
                st.markdown(f"#### 🏠 {g_sel['home']} (Home)")
                xba_h, xslg_h = (h_home['xBA'].mean(), h_home['xSLG'].mean()) if not h_home.empty else (0.240, 0.400)
                
                # Injeksi Pengaruh Bullpen Lawan (b_era_away) ke Proyeksi Home
                bp_mod_h = b_era_away / 4.00
                proj_r_h = round(((h_home['xwOBA_vs_R'].mean() * 12) + (xslg_h * 2)) * bp_mod_h, 1) if not h_home.empty else round(4.0 * bp_mod_h, 1)
                
                st.write(f"📈 Proyeksi Team Runs: **{proj_r_h}**")
                st.caption(f"🏏 Proyeksi Singles: **{round((xba_h * 25) * bp_mod_h, 1)}** | Doubles: **{round((xslg_h * 4.5) * bp_mod_h, 1)}**")
                st.write(f"🛡️ **Team Bullpen ERA:** {b_era_home}")
            
            st.divider()
            st.markdown("### ⚔️ Analisis H2H Tim & Prediksi ML / Handicap")
            score_away = h_away['xwOBA_vs_R'].mean() if not h_away.empty else 0.300
            score_home = h_home['xwOBA_vs_R'].mean() if not h_home.empty else 0.300
            
            diff = (score_away - (b_era_home / 15)) - (score_home - (b_era_away / 15))
            if diff > 0:
                fav_team, dog_team, win_prob = g_sel['away'], g_sel['home'], min(round(55 + (abs(diff) * 150), 1), 78.0)
            else:
                fav_team, dog_team, win_prob = g_sel['home'], g_sel['away'], min(round(55 + (abs(diff) * 150), 1), 78.0)
            
            c_h2h1, c_h2h2 = st.columns(2)
            with c_h2h1: st.success(f"🔮 **Moneyline:** {fav_team} (Probabilitas: {win_prob}%)")
            with c_h2h2:
                opp_b_era = b_era_home if fav_team == g_sel['away'] else b_era_away
                if win_prob >= 60.0 and opp_b_era >= 4.00: st.error(f"📐 **Handicap:** {fav_team} -1.5 (🔥 Bullpen Lawan Rapuh)")
                else: st.warning(f"📐 **Handicap:** {dog_team} +1.5 (Laga Ketat / Proteksi Run Line)")
                
            st.divider()
            st.markdown("### ⚡ AI Automated Same Game Parlay Builder")
            m_hitters = pd.concat([h_away, h_home])
            if not m_hitters.empty and 'HR_Prob_Score' in m_hitters.columns:
                st.markdown("#### 💣 OPSI 1: 3-Leg HR Parlay (High Risk)")
                for _, r in m_hitters.sort_values('HR_Prob_Score', ascending=False).head(3).iterrows():
                    st.write(f"- 🎯 **{r['Name']}** ({r['Team']}) ➔ **OVER 0.5 Home Run** *(Score: {r['HR_Prob_Score']})*")
                st.markdown("#### 🏏 OPSI 2: 4-Leg Total Base Parlay (Solid)")
                for _, r in m_hitters.sort_values('xSLG', ascending=False).head(4).iterrows():
                    st.write(f"- ⚾ **{r['Name']}** ({r['Team']}) ➔ **OVER 1.5 Total Bases** *(xSLG: {r['xSLG']})*")

    # --- TAB 8: RESTORED FULL CROSS-GAME ENGINE ---
    with tabs[7]:
        st.subheader("🌍 Cross-Game Multi-Match Parlay Engine")
        st.write("Sistem menyaring secara ketat maksimal 1 pemain per pertandingan untuk dikombinasikan lintas laga harian.")
        if len(game_details) < 2: 
            st.warning("⚠️ Diperlukan minimal 2 pertandingan aktif di tanggal ini.")
        elif not df_hitters.empty:
            pool_hit, pool_power, pool_mix = [], [], []
            for game in game_details:
                g_hitters = df_hitters[df_hitters['Team'].isin([game['away'], game['home']])]
                if not g_hitters.empty:
                    top_h = g_hitters.sort_values('xBA', ascending=False).iloc[0]
                    pool_hit.append({'name': top_h['Name'], 'team': top_h['Team'], 'stat': f"xBA: {top_h['xBA']}", 'game': game['text']})
                    top_p = g_hitters.sort_values('HR_Prob_Score', ascending=False).iloc[0]
                    pool_power.append({'name': top_p['Name'], 'team': top_p['Team'], 'stat': f"AI Score: {top_p['HR_Prob_Score']}", 'game': game['text']})
                    top_m = g_hitters.sort_values('xwOBA', ascending=False).iloc[0]
                    pool_mix.append({'name': top_m['Name'], 'team': top_m['Team'], 'stat': f"xwOBA: {top_m['xwOBA']}", 'game': game['text']})
            
            c_slip1, c_slip2 = st.columns(2)
            with c_slip1:
                st.markdown("### 🟢 SLIP 1: Raja Kontak Lintas Laga (3-5 Legs)")
                for i in range(min(len(pool_hit), 4)): st.success(f"**Leg {i+1}:** {pool_hit[i]['name']} ({pool_hit[i]['team']}) ➔ **OVER 0.5 HIT** *({pool_hit[i]['stat']} | {pool_hit[i]['game']})*")
                st.markdown("### 💣 SLIP 2: Tiket Boom Home Run Lintas Laga (3 Legs)")
                for i in range(min(len(pool_power), 3)): st.error(f"**Leg {i+1}:** {pool_power[i]['name']} ({pool_power[i]['team']}) ➔ **OVER 0.5 HR** *({pool_power[i]['stat']} | {pool_power[i]['game']})*")
                st.markdown("### 🎯 SLIP 3: Target Eksploitasi Pelempar (4 Legs)")
                for i in range(min(len(pool_hit), max(len(pool_hit)-1, 1))):
                    if i < 4: st.info(f"**Leg {i+1}:** {pool_hit[i]['name']} ({pool_hit[i]['team']}) ➔ **OVER 1.5 TB** *({pool_hit[i]['game']})*")
            with c_slip2:
                st.markdown("### 🥗 SLIP 4: Harian Monster Mix Lintas Laga (5 Legs)")
                for i in range(min(len(game_details), 5)):
                    if i % 3 == 0: st.warning(f"**Leg {i+1}:** {pool_mix[i]['name']} ({pool_mix[i]['team']}) ➔ **OVER 0.5 RUN** *({pool_mix[i]['game']})*")
                    elif i % 3 == 1: st.success(f"**Leg {i+1}:** {pool_hit[i]['name']} ({pool_hit[i]['team']}) ➔ **OVER 0.5 HIT** *({pool_hit[i]['game']})*")
                    else: st.info(f"**Leg {i+1}:** {pool_power[i]['name']} ({pool_power[i]['team']}) ➔ **OVER 1.5 TB** *({pool_power[i]['game']})*")
                
                st.markdown("### 🏆 SLIP 5: The Ultimate Longshot Parlay (6-8 Legs)")
                for i in range(min(len(game_details), 8)):
                    prop_t = "OVER 0.5 HIT" if i % 2 == 0 else "OVER 1.5 TOTAL BASES"
                    st.warning(f"**Leg {i+1}:** {pool_hit[i]['name']} ({pool_hit[i]['team']}) ➔ **{prop_t}** *(Laga: {pool_hit[i]['game']})*")

    # --- TAB 9: THE FINAL SLIPS (INTACT WITH ALL FIXES) ---
    with tabs[8]:
        st.subheader("🎯 THE FINAL SLIPS: Auto-Veto, 14d Form, & Lotto Command Center")
        st.write("Sistem menyaring pemain menggunakan urutan prioritas berlapis: Veto Platoon ➔ Batting Order Top 5 ➔ Klasifikasi Gaya Main.")
        
        if df_hitters.empty or not game_details:
            st.warning("Data harian belum siap.")
        else:
            vetoed = []
            for game in game_details:
                for team, opp_hand, opp_p, opp_team in [(game['away'], game['home_hand'], game['home_pitcher'], game['home']), (game['home'], game['away_hand'], game['away_pitcher'], game['away'])]:
                    p_hand = opp_hand if opp_hand in ['L', 'R'] else 'R'
                    opp_bullpen = fallback_bullpen_era.get(opp_team, 4.15)
                    
                    for _, h in df_hitters[df_hitters['Team'] == team].iterrows():
                        split_col = f'xwOBA_vs_{p_hand}'
                        split_score = h[split_col] if split_col in df_hitters.columns else h.get('xwOBA', 0)
                        
                        b_order = h.get('Batting_Order', 3) 
                        l14_xwoba = h.get('xwOBA_L14', h.get('xwOBA', 0))
                        l14_pa = h.get('PA_L14', 40)
                        
                        if split_score >= 0.340:
                            h_dict = h.to_dict()
                            h_dict.update({
                                'Game': game['text'], 'Opp_Pitcher': opp_p, 'Veto_Score': split_score,
                                'Batting_Order': b_order, 'xwOBA_L14': l14_xwoba, 'PA_L14': l14_pa, 'Opp_Bullpen_ERA': opp_bullpen
                            })
                            vetoed.append(h_dict)
            
            df_v = pd.DataFrame(vetoed)
            if df_v.empty:
                st.error("🚨 Tidak ada pemain yang lolos sensor ketat Veto Platoon hari ini. Mesin menyarankan NO BET.")
            else:
                st.info(f"✅ Veto Engine Selesai: Berhasil menyaring **{len(df_v)} pemain elit** yang siap dieksploitasi.")
                
                st.markdown("---")
                st.markdown("### 🎯 SLIP 1: The Sniper Parlay (Pure Data - Dynamic Sizing)")
                st.caption("SOP Ketat: Wajib lolos Veto (>0.340) DAN prioritas urutan Top 5 Batting Order.")
                
                # Filter utama: Cari yang urutan pukulnya 1-5
                df_sniper_pool = df_v[df_v['Batting_Order'] <= 5].sort_values('xBA', ascending=False)
                
                # FALLBACK (Kopling Otomatis): Kalau kosong, abaikan urutan pukul, ambil xBA tertinggi yang lolos Veto
                if df_sniper_pool.empty:
                    st.info("⚠️ Data urutan pukul 1-5 kosong. Sistem mengambil alih dengan pemain xBA tertinggi dari seluruh daftar Veto.")
                    df_sniper_pool = df_v.sort_values('xBA', ascending=False)
                
                legs_count = min(len(df_sniper_pool), 3)
                st.write(f"💡 *Sistem merekomendasikan tiket **{legs_count}-Leg Parlay** berdasarkan ketersediaan data murni hari ini.*")
                l_no = 1
                for _, r in df_sniper_pool.head(legs_count).iterrows():
                    prop = "OVER 0.5 HIT" if l_no <= 2 else "OVER 1.5 TOTAL BASES"
                    st.success(f"**Leg {l_no}:** {r['Name']} ({r['Team']}) ➔ **{prop}** *(Urutan Pukul #{r.get('Batting_Order', '?')} | vs {r['Opp_Pitcher']} 🟢)*")
                    l_no += 1

                st.markdown("---")
                st.markdown("### 🔥 SLIP 2: The Hot Hand Parlay (Momentum Wangi L14)")
                st.caption("SOP: Mengabaikan statistik musim penuh, murni mencari pemain yang pemukulannya paling panas dalam 2 minggu terakhir.")
                
                df_hot_pool = df_v.sort_values('xwOBA_L14', ascending=False).head(3)
                l_no = 1
                for _, r in df_hot_pool.iterrows():
                    st.warning(f"**Leg {l_no}:** {r['Name']} ({r['Team']}) ➔ **OVER 0.5 HIT / OVER 1.5 TB** *(xwOBA 14 Hari Terakhir: {r['xwOBA_L14']} 🔥)*")
                    l_no += 1

                st.markdown("---")
                st.markdown("### 🔗 SLIP 3: The Narrative SGP (Korelasi & Eksploitasi Bullpen)")
                st.caption("SOP: Mencari 1 laga harian di mana tim lawan memiliki Bullpen ERA paling hancur untuk dieksploitasi sampai akhir laga.")
                
                best_sgp_game = df_v.sort_values('Opp_Bullpen_ERA', ascending=False).iloc[0]['Game']
                df_sgp_match = df_v[df_v['Game'] == best_sgp_game].sort_values('Veto_Score', ascending=False).head(3)
                
                st.markdown(f"**📍 Target Match:** {best_sgp_game} *(Mengincar Bullpen Lawan dengan ERA: {df_v.sort_values('Opp_Bullpen_ERA', ascending=False).iloc[0]['Opp_Bullpen_ERA']} 🟥)*")
                l_no = 1
                for _, r in df_sgp_match.iterrows():
                    if l_no == 1: st.info(f"**Leg 1:** {r['Name']} ➔ **OVER 0.5 HIT**")
                    elif l_no == 2: st.info(f"**Leg 2:** {r['Name']} ➔ **OVER 0.5 RUN** *(Urutan Pukul #{r['Batting_Order']})*")
                    else: st.info(f"**Leg 3:** {r['Name']} ➔ **OVER 0.5 RBI**")
                    l_no += 1

                st.markdown("---")
                st.markdown("### 🎰 THE DEGENERATE LOTTO & HOME RUN SPECIALS (High Risk / Low Stake)")
                c_hr1, c_hr2 = st.columns(2)
                used_hr_names = set()
                
                with c_hr1:
                    st.markdown("#### 🧨 SLIP 4: Vetoed Elite HR Parlay (3 Legs)")
                    slip4 = df_v.sort_values('Barrel%', ascending=False).head(3)
                    for i, (idx, r) in enumerate(slip4.iterrows()):
                        used_hr_names.add(r['Name'])
                        st.error(f"**Leg {i+1}:** {r['Name']} ({r['Team']}) ➔ **OVER 0.5 HOME RUN** *(Barrel: {r['Barrel%']}% | Order #{r['Batting_Order']})*")
                
                with c_hr2:
                    st.markdown("#### 🚀 SLIP 5: The Ultimate Lotto Longshot (5-7 Legs)")
                    st.caption("Perkalian Odds Raksasa dari gabungan pemain lolos veto teratas lintas laga.")
                    slip5 = df_v[~df_v['Name'].isin(used_hr_names)].sort_values('Max EV', ascending=False).head(5)
                    if len(slip5) < 3:
                        st.write("Data tidak cukup untuk menyusun Lotto tanpa duplikasi pemain.")
                    else:
                        for i, (idx, r) in enumerate(slip5.iterrows()):
                            st.error(f"**Leg {i+1}:** {r['Name']} ({r['Team']}) ➔ **OVER 1.5 TOTAL BASES** *(Max EV: {r['Max EV']} Mph)*")
