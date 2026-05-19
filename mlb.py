import streamlit as st
import pandas as pd
import statsapi
import pytz
from datetime import datetime

st.set_page_config(page_title="MLB AI Props Dashboard", layout="wide")
st.title("⚾ MLB Daily Matchup, AI Predictions & Parlay Command Center")

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
@st.cache_data(ttl=86400)
def get_pitcher_hand(name):
    """Mencari tangan pelempar (L/R) dengan interogasi ID MLB profil"""
    if not name or name in ['Unknown Pitcher', 'Unknown', 'TBD']: return "-"
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
def get_daily_schedule():
    games = statsapi.schedule(date=mlb_date_str)
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
        st.error("⚠️ File CSV belum siap!")
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
                    hitters.append({'Team': abbr, 'Name': name, 'AB': b.get('atBats', 0), 'H': b.get('hits', 0), 'HR': b.get('homeRuns', 0), 'RBI': b.get('rbi', 0), 'TB': b.get('totalBases', b.get('hits', 0))})
                if p and p.get('battersFaced', 0) > 0:
                    pitchers.append({'Team': abbr, 'Name': name, 'IP': str(p.get('inningsPitched', '0.0')), 'H Allowed': p.get('hits', 0), 'SO': p.get('strikeOuts', 0)})
        return pd.DataFrame(hitters), pd.DataFrame(pitchers)
    except: return pd.DataFrame(), pd.DataFrame()

playing_teams, today_matchups, player_team_map, game_details = get_daily_schedule()
df_hitters, df_pitchers = load_local_data()
if not df_hitters.empty: df_hitters.insert(1, 'Team', df_hitters['Name'].map(player_team_map))
if not df_pitchers.empty: df_pitchers.insert(1, 'Team', df_pitchers['Name'].map(player_team_map))

# --- UI MAIN ---
if not today_matchups:
    st.warning("Tidak ada jadwal pertandingan MLB hari ini.")
else:
    st.markdown("### 🏟️ Slate Summary")
    cols = st.columns(min(len(today_matchups), 6))
    for i, m in enumerate(today_matchups): cols[i % 6].info(m)

    tabs = st.tabs(["Pitchers", "Hitters", "🔥 Top Picks", "🚀 AI Pred", "📡 Live", "📈 Accuracy", "🔮 SGP", "🌍 Cross-Match", "🎯 FINAL SLIPS"])

    with tabs[0]:
        st.subheader("Pitcher Metrics Allowed")
        if not df_pitchers.empty:
            df_p_today = df_pitchers[df_pitchers['Team'].isin(playing_teams)].dropna(subset=['Team'])
            st.dataframe(df_p_today.style.background_gradient(cmap='RdYlGn', subset=[c for c in ['xwOBA Allowed', 'xSLG Allowed', 'xBA Allowed'] if c in df_p_today.columns]), use_container_width=True)

    with tabs[1]:
        st.subheader("Hitter Advanced Metrics")
        if not df_hitters.empty:
            df_h_today = df_hitters[df_hitters['Team'].isin(playing_teams)].dropna(subset=['Team'])
            st.dataframe(df_h_today.sort_values(by='xwOBA', ascending=False).head(50), use_container_width=True)

    with tabs[2]:
        st.subheader("🤖 Rekomendasi Pick Per Pertandingan")
        for game in game_details:
            with st.expander(f"⚾ {game['away']} @ {game['home']}"):
                h_df = df_hitters[df_hitters['Team'].isin([game['away'], game['home']])]
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("### 🏏 Hitters")
                    if not h_df.empty:
                        t_hr = h_df.sort_values('Barrel%', ascending=False).iloc[0]
                        st.success(f"**1. Over HR:** {t_hr['Name']} ({t_hr['Team']})\n\n↳ *Barrel: {t_hr['Barrel%']}%*")
                        t_tb = h_df.sort_values('xSLG', ascending=False).iloc[0]
                        st.info(f"**2. Over TB:** {t_tb['Name']}\n\n↳ *xSLG: {t_tb['xSLG']}*")
                        t_ba = h_df.sort_values('xBA', ascending=False).iloc[0]
                        st.success(f"**5. Over Hit:** {t_ba['Name']}\n\n↳ *xBA: {t_ba['xBA']}*")
                with c2:
                    st.markdown("### 🎯 Pitchers")
                    for p_name, p_team, p_hand in [(game['away_pitcher'], game['away'], game['away_hand']), (game['home_pitcher'], game['home'], game['home_hand'])]:
                        if p_name != 'Unknown Pitcher':
                            st.info(f"⚾ **{p_name}** ({p_team} - {p_hand})")

    with tabs[3]:
        st.subheader("🚀 AI Prop Modeling")
        for game in game_details:
            with st.expander(f"🔥 Prediction: {game['text']}"):
                c_a, c_h = st.columns(2)
                for c, t in [(c_a, game['away']), (c_h, game['home'])]:
                    with c:
                        df_t = df_hitters[df_hitters['Team'] == t]
                        if not df_t.empty: st.dataframe(df_t.sort_values('HR_Prob_Score', ascending=False).head(5)[['Name', 'HR_Prob_Score', 'xwOBA_vs_R', 'xwOBA_vs_L']], hide_index=True)

    with tabs[4]:
        st.subheader("📡 Live Report")
        for game in game_details:
            if game['status'] != 'Scheduled':
                with st.expander(f"🔥 {game['text']}"):
                    l_h, _ = get_live_boxscore(game['game_id'], game['away'], game['home'])
                    if not l_h.empty: st.dataframe(l_h[(l_h['H'] >= 1) | (l_h['HR'] >= 1)], hide_index=True, use_container_width=True)

    with tabs[5]:
        st.subheader("📈 Accuracy Tracker")
        st.write("Verifikasi 22 target otomatis per game...")

    with tabs[6]:
        st.subheader("🔮 SGP Builder")
        if not df_hitters.empty:
            sel_match = st.selectbox("🎯 Pilih Laga SGP:", [g['text'] for g in game_details])
            st.write(f"Analisis SGP untuk {sel_match}...")

    with tabs[7]:
        st.subheader("🌍 Cross-Game Parlay")
        st.write("Sistem diversifikasi 1 pemain per pertandingan.")

    # --- TAB 9: THE FINAL 5 SLIPS ---
    with tabs[8]:
        st.subheader("🎯 THE FINAL 5 SLIPS (Vetoed & AI Optimized)")
        st.write("Alur: Veto Platoon (xwOBA > 0.340) ➔ Diversifikasi Lintas Laga ➔ Korelasi Match ➔ HR Specialized Slips.")
        
        if df_hitters.empty or not game_details:
            st.warning("Data belum siap.")
        else:
            # --- VETO ENGINE ---
            vetoed = []
            for game in game_details:
                for team, opp_hand, opp_p in [(game['away'], game['home_hand'], game['home_pitcher']), (game['home'], game['away_hand'], game['away_pitcher'])]:
                    p_hand = opp_hand if opp_hand in ['L', 'R'] else 'R'
                    for _, h in df_hitters[df_hitters['Team'] == team].iterrows():
                        split_score = h[f'xwOBA_vs_{p_hand}'] if f'xwOBA_vs_{p_hand}' in df_hitters.columns else h.get('xwOBA', 0)
                        if split_score >= 0.340:
                            h_dict = h.to_dict()
                            h_dict.update({'Game': game['text'], 'Opp_Pitcher': opp_p, 'Veto_Score': split_score})
                            vetoed.append(h_dict)
            
            df_v = pd.DataFrame(vetoed)
            if df_v.empty:
                st.error("🚨 Tidak ada pemain lolos Veto Platoon hari ini.")
            else:
                st.info(f"✅ Lolos Veto: {len(df_v)} Pemain.")
                
                # --- SLIP 1, 2, 3 ---
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("### 🏆 SLIP 1: Foundation (Aman)")
                    for i, r in df_v.sort_values('xBA', ascending=False).head(3).iterrows():
                        st.success(f"**L{i+1}:** {r['Name']} ➔ **OVER 0.5 HIT** ({r['Veto_Score']} 🟢)")
                
                with c2:
                    st.markdown("### 🔥 SLIP 2: Correlated SGP")
                    best_g = df_v['Game'].value_counts().idxmax()
                    for i, r in df_v[df_v['Game'] == best_g].sort_values('Veto_Score', ascending=False).head(3).iterrows():
                        st.warning(f"**L{i+1}:** {r['Name']} ➔ **OVER 0.5 HIT/RUN** ({best_g})")
                
                st.divider()
                st.markdown("### 🚀 SLIP 3: The 'Go Big' Mix")
                c3, c_fade = st.columns([3, 1])
                with c3:
                    for i, r in df_v.sort_values('xSLG', ascending=False).head(3).iterrows():
                        st.info(f"**Leg {i+1}:** {r['Name']} ➔ **OVER 1.5 TB** ({r['Veto_Score']} 🟢)")
                with c_fade:
                    if not df_pitchers.empty:
                        f_p = df_pitchers.sort_values('xBA Allowed', ascending=False).iloc[0]
                        st.error(f"**Leg 4 Fade:** {f_p['Name']} ➔ **OVER HIT ALLOWED**")

                # --- SLIP 4 & 5: HOME RUN SPECIALS ---
                st.divider()
                st.markdown("### 💣 THE HOME RUN SPECIALS (High Risk / High Reward)")
                c_hr1, c_hr2 = st.columns(2)
                
                used_hr_names = set()
                
                with c_hr1:
                    st.markdown("#### 🧨 SLIP 4: Vetoed Elite HR (3-Leg)")
                    # Ambil 3 pemain vetoed dengan Barrel% tertinggi
                    slip4 = df_v.sort_values('Barrel%', ascending=False).head(3)
                    for i, r in slip4.iterrows():
                        used_hr_names.add(r['Name'])
                        st.error(f"**Leg {i+1}:** {r['Name']} ({r['Team']}) ➔ **OVER 0.5 HOME RUN**\n\n↳ *Barrel: {r['Barrel%']}% | vs {r['Opp_Pitcher']}*")
                
                with c_hr2:
                    st.markdown("#### 🚀 SLIP 5: Vetoed Darkhorse HR (4-Leg)")
                    # Ambil 4 pemain vetoed yang TIDAK ADA di Slip 4, urutkan berdasarkan Max EV
                    slip5 = df_v[~df_v['Name'].isin(used_hr_names)].sort_values('Max EV', ascending=False).head(4)
                    if len(slip5) < 4:
                        st.write("Pemain lolos veto tidak cukup untuk menyusun slip darkhorse tanpa duplikasi.")
                    else:
                        for i, r in slip5.iterrows():
                            st.error(f"**Leg {i+1}:** {r['Name']} ({r['Team']}) ➔ **OVER 0.5 HOME RUN**\n\n↳ *Max EV: {r['Max EV']} mph | vs {r['Opp_Pitcher']}*")
