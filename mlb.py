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

# Fitur Mesin Waktu (Date Picker) di Sidebar
st.sidebar.header("⚙️ Kontrol Waktu")
st.sidebar.write("Gunakan kalender ini untuk mengecek prediksi dan hasil pertandingan kemarin/hari sebelumnya.")
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
        st.error("⚠️ File CSV belum siap! Pastikan data Fase 1 & 2 di GitHub sudah diproses.")
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

# Perhatikan bahwa sekarang get_daily_schedule menerima mlb_date_str
playing_teams, today_matchups, player_team_map, game_details = get_daily_schedule(mlb_date_str)
df_hitters, df_pitchers = load_local_data()

if not df_hitters.empty: df_hitters.insert(1, 'Team', df_hitters['Name'].map(player_team_map))
if not df_pitchers.empty: df_pitchers.insert(1, 'Team', df_pitchers['Name'].map(player_team_map))

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
        st.subheader("Pitcher Metrics Allowed (Statcast)")
        if not df_pitchers.empty:
            df_p_today = df_pitchers[df_pitchers['Team'].isin(playing_teams)].dropna(subset=['Team'])
            allowed_metrics = [c for c in ['xwOBA Allowed', 'xSLG Allowed', 'xBA Allowed'] if c in df_p_today.columns]
            st.dataframe(df_p_today.style.background_gradient(cmap='RdYlGn', subset=allowed_metrics) if allowed_metrics else df_p_today, use_container_width=True, height=500)

    with tabs[1]:
        st.subheader("Hitter Advanced & Platoon Metrics")
        if not df_hitters.empty:
            df_h_today = df_hitters[df_hitters['Team'].isin(playing_teams)].dropna(subset=['Team'])
            col1, col2 = st.columns(2)
            with col1: search_name = st.text_input("🔍 Ketik Nama Pemain:", "", key="tab2_s")
            with col2: sel_team = st.selectbox("Filter Tim:", ["Semua Tim"] + sorted(df_h_today['Team'].unique().tolist()), key="tab2_t")
            display_df = df_h_today[df_h_today['Name'].str.contains(search_name, case=False, na=False)] if search_name else (df_h_today[df_h_today['Team'] == sel_team] if sel_team != "Semua Tim" else df_h_today.sort_values(by='xwOBA', ascending=False).head(50))
            metrics = [c for c in display_df.columns if any(k in c for k in ['xwOBA', 'xBA', 'xSLG', 'HardHit'])]
            st.dataframe(display_df.style.background_gradient(cmap='RdYlGn', subset=metrics) if metrics else display_df, use_container_width=True, height=500)

    # --- TAB 3: DAILY TOP PICKS (DENGAN FIX INDEX ERROR PITCHER) ---
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
                            # FIX ERROR: Pastikan p_name adalah string valid dan tidak kosong
                            if p_name and isinstance(p_name, str) and p_name.strip() and p_name not in ['Unknown Pitcher', 'Unknown', 'TBD']:
                                last_name = p_name.split()[-1]
                                p_match = df_p_today[(df_p_today['Team'] == p_team) & (df_p_today['Name'].str.contains(last_name, case=False, na=False))]
                                if not p_match.empty:
                                    p_stat = p_match.iloc[0]
                                    xba_alwd = p_stat.get('xBA Allowed', 0.250)
                                    xwoba_alwd = p_stat.get('xwOBA Allowed', 0.320)
                                    hit_rec = "OVER Hit Allowed" if xba_alwd >= 0.250 else "UNDER Hit Allowed"
                                    out_rec = "UNDER Outs Recorded" if xwoba_alwd >= 0.330 else "OVER Outs Recorded"
                                    st.info(f"⚾ **{p_stat['Name']}** ({p_team} - {p_hand})\n\n↳ **Target 1: {hit_rec}** *(xBA Allowed: {xba_alwd})*\n\n↳ **Target 2: {out_rec}** *(xwOBA Allowed: {xwoba_alwd})*")
                                else: st.write(f"⚾ **{p_name}** ({p_team} - {p_hand}) - *Metrik Statcast belum cukup*")
                            else:
                                st.write(f"⚾ **Pitcher Belum Ditentukan** ({p_team})")

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
                with st.expander(f"⏳ {game['away']} @ {game['home']}", expanded=False): 
                    st.info("Pertandingan belum dimulai.")
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

    with tabs[6]:
        st.subheader("🔮 AI Game Props & Same Game Parlay (SGP) Builder")
        if not game_details:
            st.info("Tidak ada pertandingan yang tersedia.")
        elif not df_hitters.empty and not df_pitchers.empty:
            game_opts = [g['text'] for g in game_details]
            sel_match = st.selectbox("🎯 Pilih Pertandingan untuk Racikan SGP:", game_opts, key="tab7_match_select")
            g_sel = next(g for g in game_details if g['text'] == sel_match)
            
            w_cond, wind_cond = get_weather_info(g_sel['game_id'])
            st.info(f"🏟️ Stadion: {g_sel['venue']} | 🌤️ Cuaca: {w_cond} | 💨 Angin: {wind_cond}")
            
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
            st.markdown("### ⚔️ Analisis H2H Tim & Prediksi ML / Handicap")
            score_away = h_away['xwOBA_vs_R'].mean() if not h_away.empty else 0.300
            score_home = h_home['xwOBA_vs_R'].mean() if not h_home.empty else 0.300
            diff = abs(score_away - score_home)
            if score_away > score_home:
                fav_team, dog_team = g_sel['away'], g_sel['home']
                win_prob = min(round(50 + (diff * 200), 1), 78.0)
            else:
                fav_team, dog_team = g_sel['home'], g_sel['away']
                win_prob = min(round(50 + (diff * 200), 1), 78.0)
            
            c_h2h1, c_h2h2 = st.columns(2)
            with c_h2h1:
                st.success(f"🔮 **Prediksi Kemenangan (Moneyline):**\n\n**{fav_team} Win Line** (Probabilitas: {win_prob}%)")
            with c_h2h2:
                if win_prob >= 58.0: st.error(f"📐 **Rekomendasi Pasar Handicap:**\n\n**{fav_team} -1.5** (Cover Spread)")
                else: st.warning(f"📐 **Rekomendasi Pasar Handicap:**\n\n**{dog_team} +1.5** (Run-Line Protection)")
            
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

    with tabs[8]:
        st.subheader("🎯 THE FINAL 5 SLIPS (Vetoed & AI Optimized)")
        st.write("Kombinasi taktis berbasis SOP: Veto Platoon (xwOBA > 0.340) ➔ Diversifikasi Lintas Laga ➔ Korelasi Match ➔ HR Specialized Slips.")
        
        if df_hitters.empty or not game_details:
            st.warning("Data harian belum siap.")
        else:
            # --- VETO ENGINE CORNER ---
            vetoed = []
            for game in game_details:
                for team, opp_hand, opp_p in [(game['away'], game['home_hand'], game['home_pitcher']), (game['home'], game['away_hand'], game['away_pitcher'])]:
                    p_hand = opp_hand if opp_hand in ['L', 'R'] else 'R'
                    for _, h in df_hitters[df_hitters['Team'] == team].iterrows():
                        split_col = f'xwOBA_vs_{p_hand}'
                        split_score = h[split_col] if split_col in df_hitters.columns else h.get('xwOBA', 0)
                        if split_score >= 0.340:
                            h_dict = h.to_dict()
                            h_dict.update({'Game': game['text'], 'Opp_Pitcher': opp_p, 'Veto_Score': split_score})
                            vetoed.append(h_dict)
            
            df_v = pd.DataFrame(vetoed)
            if df_v.empty:
                st.error("🚨 PERINGATAN: Tidak ada pemain lolos Veto Platoon (Semua skor vs Pitcher < 0.340).")
            else:
                st.info(f"✅ Veto Engine Selesai: Berhasil menyaring **{len(df_v)} pemain** dengan indeks kekuatan hijau pekat.")
                
                c_fin1, c_fin2 = st.columns(2)
                with c_fin1:
                    st.markdown("### 🏆 FINAL SLIP 1: Vetoed Foundation (Aman)")
                    safe_pool = df_v.sort_values('xBA', ascending=False).head(3)
                    leg_no = 1
                    for _, r in safe_pool.iterrows():
                        prop = "OVER 0.5 HIT" if leg_no <= 2 else "OVER 1.5 TOTAL BASES"
                        st.success(f"**Leg {leg_no}:** {r['Name']} ({r['Team']}) ➔ **{prop}** *(Veto vs {r['Opp_Pitcher']}: Score {r['Veto_Score']} 🟢)*")
                        leg_no += 1
                
                with c_fin2:
                    st.markdown("### 🔥 FINAL SLIP 2: Correlated SGP (Tab 7 Logic)")
                    best_g = df_v['Game'].value_counts().idxmax()
                    sgp_pool = df_v[df_v['Game'] == best_g].sort_values('Veto_Score', ascending=False).head(3)
                    st.markdown(f"**📍 Target Match:** {best_g}")
                    leg_sgp = 1
                    for _, r in sgp_pool.iterrows():
                        if leg_sgp == 1: st.info(f"**Leg 1:** {r['Name']} ➔ **OVER 0.5 HIT**")
                        elif leg_sgp == 2: st.warning(f"**Leg 2:** {r['Name']} ➔ **OVER 0.5 RUN**")
                        else: st.error(f"**Leg 3:** {r['Name']} ➔ **OVER 0.5 RBI**")
                        leg_sgp += 1
                
                st.divider()
                st.markdown("### 🚀 FINAL SLIP 3: The 'Go Big' Mix (4 Legs)")
                c3, c_fade = st.columns([3, 1])
                with c3:
                    mix_pool = df_v.sort_values('xSLG', ascending=False).head(3)
                    leg_mix = 1
                    for _, r in mix_pool.iterrows():
                        st.info(f"**Leg {leg_mix}:** {r['Name']} ({r['Team']}) ➔ **OVER 1.5 TOTAL BASES** *(Veto Score: {r['Veto_Score']})*")
                        leg_mix += 1
                with c_fade:
                    if not df_pitchers.empty and 'xBA Allowed' in df_pitchers.columns:
                        f_p = df_pitchers.sort_values('xBA Allowed', ascending=False).iloc[0]
                        st.error(f"**Leg 4 (Pitcher Fade):**\n\n{f_p['Name']} ➔ **OVER HIT ALLOWED**")

                st.divider()
                st.markdown("### 💣 THE HOME RUN SPECIALS (High Risk / High Reward)")
                c_hr1, c_hr2 = st.columns(2)
                used_hr_names = set()
                
                with c_hr1:
                    st.markdown("#### 🧨 FINAL SLIP 4: Vetoed Elite HR (3-Leg)")
                    slip4 = df_v.sort_values('Barrel%', ascending=False).head(3)
                    for i, (idx, r) in enumerate(slip4.iterrows()):
                        used_hr_names.add(r['Name'])
                        st.error(f"**Leg {i+1}:** {r['Name']} ({r['Team']}) ➔ **OVER 0.5 HOME RUN**\n\n↳ *Barrel: {r['Barrel%']}% | vs {r['Opp_Pitcher']}*")
                
                with c_hr2:
                    st.markdown("#### 🚀 FINAL SLIP 5: Vetoed Darkhorse HR (4-Leg)")
                    slip5 = df_v[~df_v['Name'].isin(used_hr_names)].sort_values('Max EV', ascending=False).head(4)
                    if len(slip5) < 4:
                        st.write("Pemain lolos veto tidak cukup untuk menyusun slip darkhorse tanpa duplikasi.")
                    else:
                        for i, (idx, r) in enumerate(slip5.iterrows()):
                            st.error(f"**Leg {i+1}:** {r['Name']} ({r['Team']}) ➔ **OVER 0.5 HOME RUN**\n\n↳ *Max EV: {r['Max EV']} mph | vs {r['Opp_Pitcher']}*")
