import pybaseball as pyb
import pandas as pd
import pytz
from datetime import datetime, timedelta

pyb.cache.enable()

def run_pipeline():
    print("🤖 Memulai MLB AI Predictive Pipeline (Phase 1: Platoon Splits)...")
    print("================================================================")
    
    wib_tz = pytz.timezone('Asia/Jakarta')
    est_tz = pytz.timezone('US/Eastern')
    now_est = datetime.now(wib_tz).astimezone(est_tz)
    today_str = now_est.strftime('%Y-%m-%d')
    
    # Tarik data dari awal musim MLB 2026 (Maret)
    start_season_str = '2026-03-20'
    
    # --- 1. DOWNLOAD BASE HITTER DATA ---
    print("⏳ [1/4] Mengunduh Base Metrics Full Season Hitters...")
    try:
        barrels_df = pyb.statcast_batter_exitvelo_barrels(2026, minBBE=10)
        xstats_df = pyb.statcast_batter_expected_stats(2026, minPA=10)
        
        b_cols = [c for c in ['player_id', 'last_name, first_name', 'attempts', 'ev95percent', 'brl_percent', 'max_hit_speed'] if c in barrels_df.columns]
        x_cols = [c for c in ['player_id', 'est_ba', 'est_slg', 'est_woba'] if c in xstats_df.columns]
        
        df_hitters = pd.merge(barrels_df[b_cols], xstats_df[x_cols], on='player_id', how='inner')
    except Exception as e:
        print(f"❌ Gagal unduh data Hitter utama: {e}")
        return

    # --- 2. DOWNLOAD & BEDAH DATA PITCH-BY-PITCH (PLATOON & 14-DAY) ---
    print("⏳ [2/4] Menggali Data Statcast Raksasa untuk Platoon Splits...")
    try:
        # Tarik data lemparan sepanjang musim
        sc_data = pyb.statcast(start_dt=start_season_str, end_dt=today_str)
        
        if not sc_data.empty:
            # Filter hanya lemparan yang dipukul (Batted Balls / 'X')
            bbe = sc_data[sc_data['type'] == 'X'].copy()
            bbe['game_date'] = pd.to_datetime(bbe['game_date'])
            
            # Ubah data ke numerik
            bbe['launch_speed'] = pd.to_numeric(bbe['launch_speed'], errors='coerce').fillna(0)
            bbe['launch_angle'] = pd.to_numeric(bbe['launch_angle'], errors='coerce').fillna(-999)
            bbe['estimated_woba_using_speedangle'] = pd.to_numeric(bbe['estimated_woba_using_speedangle'], errors='coerce').fillna(0)
            bbe['estimated_ba_using_speedangle'] = pd.to_numeric(bbe['estimated_ba_using_speedangle'], errors='coerce').fillna(0)
            
            # Bikin indikator boolean
            bbe['is_hard_hit'] = (bbe['launch_speed'] >= 95).astype(int)
            bbe['is_sweet_spot'] = ((bbe['launch_angle'] >= 8) & (bbe['launch_angle'] <= 32)).astype(int)
            
            # -----------------------------------------
            # A. EKSTRAKSI PLATOON SPLITS (VS LHP & RHP)
            # -----------------------------------------
            splits = bbe.groupby(['batter', 'p_throws']).agg(
                xBA_split=('estimated_ba_using_speedangle', 'mean'),
                xwOBA_split=('estimated_woba_using_speedangle', 'mean'),
                HardHit_split=('is_hard_hit', 'mean')
            ).reset_index()
            
            # Pivot tabel agar L dan R menjadi kolom terpisah
            splits_pivot = splits.pivot(index='batter', columns='p_throws', values=['xBA_split', 'xwOBA_split', 'HardHit_split']).reset_index()
            
            # Rapikan nama kolom hasil pivot (contoh: 'xBA_vs_L', 'xwOBA_vs_R')
            new_cols = ['player_id']
            for col in splits_pivot.columns[1:]:
                # col[0] = jenis metrik, col[1] = tangan pitcher ('L'/'R')
                metric_name = col[0].replace('_split', '')
                new_cols.append(f"{metric_name}_vs_{col[1]}")
            splits_pivot.columns = new_cols
            
            # Kalikan HardHit dengan 100 agar jadi persentase
            for c in splits_pivot.columns:
                if 'HardHit' in c:
                    splits_pivot[c] = splits_pivot[c] * 100
                    
            # Gabungkan skor Platoon ke tabel Hitter Utama
            df_hitters = pd.merge(df_hitters, splits_pivot, on='player_id', how='left')

            # -----------------------------------------
            # B. EKSTRAKSI MOMENTUM 14 HARI (14-DAY FORM)
            # -----------------------------------------
            fourteen_days_ago = pd.to_datetime((now_est - timedelta(days=14)).strftime('%Y-%m-%d'))
            recent_bbe = bbe[bbe['game_date'] >= fourteen_days_ago]
            
            if not recent_bbe.empty:
                recent_agg = recent_bbe.groupby('batter').agg(
                    is_hard_hit=('is_hard_hit', 'mean'),
                    is_sweet_spot=('is_sweet_spot', 'mean'),
                    estimated_woba_using_speedangle=('estimated_woba_using_speedangle', 'mean')
                ).reset_index()
                
                recent_agg.rename(columns={
                    'batter': 'player_id',
                    'is_hard_hit': 'HardHit% (14d)',
                    'is_sweet_spot': 'SweetSpot% (14d)',
                    'estimated_woba_using_speedangle': 'xwOBA (14d)'
                }, inplace=True)
                
                recent_agg['HardHit% (14d)'] *= 100
                recent_agg['SweetSpot% (14d)'] *= 100
                
                df_hitters = pd.merge(df_hitters, recent_agg, on='player_id', how='left')
                
    except Exception as e:
        print(f"⚠️ Terjadi masalah pada tarikan Pitch-by-Pitch: {e}")

    # --- Rapikan Data Hitter Terakhir ---
    rename_hitter = {
        'last_name, first_name': 'Name', 'attempts': 'BattedBalls',
        'ev95percent': 'HardHit%', 'brl_percent': 'Barrel%',
        'max_hit_speed': 'Max EV', 'est_ba': 'xBA', 'est_slg': 'xSLG', 
        'est_woba': 'xwOBA'
    }
    df_hitters.rename(columns=rename_hitter, inplace=True)
    if 'Name' in df_hitters.columns:
        df_hitters['Name'] = df_hitters['Name'].apply(lambda x: ' '.join(x.split(', ')[::-1]) if isinstance(x, str) and ', ' in x else x)
        
    df_hitters.fillna(0, inplace=True)

    # --- 2.5 MODELING PROBABILITAS AI (BASE) ---
    print("⏳ [2.5/4] Menghitung Baseline AI Score...")
    barrels = df_hitters['Barrel%'].astype(float)
    xslg = df_hitters['xSLG'].astype(float)
    max_ev = df_hitters['Max EV'].astype(float).replace(0, 100) # Hindari max EV 0
    hh_14d = df_hitters.get('HardHit% (14d)', pd.Series(0, index=df_hitters.index)).astype(float)
    
    xba = df_hitters['xBA'].astype(float)
    sw_14d = df_hitters.get('SweetSpot% (14d)', pd.Series(0, index=df_hitters.index)).astype(float)
    xwoba = df_hitters['xwOBA'].astype(float)
    
    df_hitters['HR_Prob_Score'] = ((barrels * 3.0) + (xslg * 40) + ((max_ev - 100).clip(lower=0) * 1.0) + (hh_14d * 0.1)).round(1)
    df_hitters['Hit_Prob_Score'] = ((xba * 200) + (sw_14d * 0.6) + (xwoba * 50)).round(1)

    # --- 3. DOWNLOAD DATA PITCHER ---
    print("⏳ [3/4] Mengunduh Metrik Allowed Pitchers...")
    try:
        p_barrels = pyb.statcast_pitcher_exitvelo_barrels(2026, minBBE=10)
        p_xstats = pyb.statcast_pitcher_expected_stats(2026, minPA=10)
        
        p_b_cols = [c for c in ['player_id', 'last_name, first_name', 'attempts', 'ev95percent', 'brl_percent'] if c in p_barrels.columns]
        p_x_cols = [c for c in ['player_id', 'est_ba', 'est_slg', 'est_woba'] if c in p_xstats.columns]
        
        df_pitchers = pd.merge(p_barrels[p_b_cols], p_xstats[p_x_cols], on='player_id', how='inner')
        
        df_pitchers.rename(columns={
            'last_name, first_name': 'Name', 'attempts': 'BattedBalls Allowed',
            'ev95percent': 'HardHit% Allowed', 'brl_percent': 'Barrel% Allowed',
            'est_ba': 'xBA Allowed', 'est_slg': 'xSLG Allowed', 'est_woba': 'xwOBA Allowed'
        }, inplace=True)

        if 'Name' in df_pitchers.columns:
            df_pitchers['Name'] = df_pitchers['Name'].apply(lambda x: ' '.join(x.split(', ')[::-1]) if isinstance(x, str) and ', ' in x else x)
    except Exception as e:
        print(f"❌ Gagal unduh data Pitcher: {e}")
        return

    # --- 4. SIMPAN CSV ---
    print("⏳ [4/4] Menyimpan ke Database Lokal...")
    df_hitters.to_csv('master_hitter_2026.csv', index=False)
    df_pitchers.to_csv('master_pitcher_2026.csv', index=False)
    
    print("✅ FASE 1 SELESAI! CSV kini memiliki data Platoon Splits (vs_L & vs_R).")

if __name__ == "__main__":
    run_pipeline()
