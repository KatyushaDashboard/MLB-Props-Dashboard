import pybaseball as pyb
import pandas as pd
import pytz
from datetime import datetime, timedelta

pyb.cache.enable()

def run_pipeline():
    print("🤖 Memulai MLB AI Predictive Pipeline...")
    print("====================================")
    
    wib_tz = pytz.timezone('Asia/Jakarta')
    est_tz = pytz.timezone('US/Eastern')
    now_est = datetime.now(wib_tz).astimezone(est_tz)
    
    # --- 1. DOWNLOAD DATA HITTER ---
    print("⏳ [1/4] Mengunduh metrik Full Season Hitters...")
    try:
        barrels_df = pyb.statcast_batter_exitvelo_barrels(2026, minBBE=10)
        xstats_df = pyb.statcast_batter_expected_stats(2026, minPA=10)
        
        b_cols = [c for c in ['player_id', 'last_name, first_name', 'attempts', 'ev95percent', 'brl_percent', 'max_hit_speed'] if c in barrels_df.columns]
        x_cols = [c for c in ['player_id', 'est_ba', 'est_slg', 'est_woba'] if c in xstats_df.columns]
        
        df_hitters = pd.merge(barrels_df[b_cols], xstats_df[x_cols], on='player_id', how='inner')
    except Exception as e:
        print(f"❌ Gagal unduh data Hitter utama: {e}")
        return

    # --- 2. DOWNLOAD DATA 14 HARI ---
    print("⏳ [2/4] Membedah data pitch-by-pitch 14 hari terakhir...")
    end_dt = now_est.strftime('%Y-%m-%d')
    start_dt = (now_est - timedelta(days=14)).strftime('%Y-%m-%d')
    
    try:
        recent_sc = pyb.statcast(start_dt=start_dt, end_dt=end_dt)
        if not recent_sc.empty:
            bbe = recent_sc[recent_sc['type'] == 'X'].copy()
            agg_dict = {}
            
            if 'launch_speed' in bbe.columns:
                bbe['launch_speed'] = pd.to_numeric(bbe['launch_speed'], errors='coerce').fillna(0)
                bbe['is_hard_hit'] = (bbe['launch_speed'] >= 95).astype(int)
                agg_dict['is_hard_hit'] = 'mean'
                
            if 'launch_angle' in bbe.columns:
                bbe['launch_angle'] = pd.to_numeric(bbe['launch_angle'], errors='coerce').fillna(-999)
                bbe['is_sweet_spot'] = ((bbe['launch_angle'] >= 8) & (bbe['launch_angle'] <= 32)).astype(int)
                agg_dict['is_sweet_spot'] = 'mean'
                
            if 'estimated_woba_using_speedangle' in bbe.columns:
                bbe['estimated_woba_using_speedangle'] = pd.to_numeric(bbe['estimated_woba_using_speedangle'], errors='coerce').fillna(0)
                agg_dict['estimated_woba_using_speedangle'] = 'mean'

            if agg_dict:
                recent_agg = bbe.groupby('batter').agg(agg_dict).reset_index()
                rename_map = {'batter': 'player_id'}
                if 'is_hard_hit' in recent_agg.columns:
                    recent_agg['is_hard_hit'] *= 100
                    rename_map['is_hard_hit'] = 'HardHit% (14d)'
                if 'is_sweet_spot' in recent_agg.columns:
                    recent_agg['is_sweet_spot'] *= 100
                    rename_map['is_sweet_spot'] = 'SweetSpot% (14d)'
                if 'estimated_woba_using_speedangle' in recent_agg.columns:
                    rename_map['estimated_woba_using_speedangle'] = 'xwOBA (14d)'
                    
                recent_agg.rename(columns=rename_map, inplace=True)
                df_hitters = pd.merge(df_hitters, recent_agg, on='player_id', how='left')
                
                for col in rename_map.values():
                    if col != 'player_id':
                        df_hitters[col] = df_hitters[col].fillna(0)
                        
    except Exception as e:
        print(f"⚠️ Melewati data 14 hari: {e}")

    # Rapikan nama kolom Hitter Full Season
    rename_hitter = {
        'last_name, first_name': 'Name', 'attempts': 'BattedBalls',
        'ev95percent': 'HardHit%', 'brl_percent': 'Barrel%',
        'max_hit_speed': 'Max EV', 'est_ba': 'xBA', 'est_slg': 'xSLG', 
        'est_woba': 'xwOBA'
    }
    df_hitters.rename(columns=rename_hitter, inplace=True)
    if 'Name' in df_hitters.columns:
        df_hitters['Name'] = df_hitters['Name'].apply(lambda x: ' '.join(x.split(', ')[::-1]) if isinstance(x, str) and ', ' in x else x)

    # --- 2.5 MODELING ALGORITMA PREDIKSI PROYEKSI (PROPS INDEX) ---
    print("⏳ [2.5/4] Menghitung skor probabilitas AI Model...")
    
    barrels = df_hitters['Barrel%'].astype(float).fillna(0)
    xslg = df_hitters['xSLG'].astype(float).fillna(0)
    max_ev = df_hitters['Max EV'].astype(float).fillna(100)
    hh_14d = df_hitters['HardHit% (14d)'].astype(float).fillna(0)
    
    xba = df_hitters['xBA'].astype(float).fillna(0)
    sw_14d = df_hitters['SweetSpot% (14d)'].astype(float).fillna(0)
    xwoba = df_hitters['xwOBA'].astype(float).fillna(0)
    
    # Eksekusi Rumus Tertimbang
    df_hitters['HR_Prob_Score'] = (barrels * 3.0) + (xslg * 40) + ((max_ev - 100).clip(lower=0) * 1.0) + (hh_14d * 0.1)
    df_hitters['Hit_Prob_Score'] = (xba * 200) + (sw_14d * 0.6) + (xwoba * 50)
    
    df_hitters['HR_Prob_Score'] = df_hitters['HR_Prob_Score'].round(1)
    df_hitters['Hit_Prob_Score'] = df_hitters['Hit_Prob_Score'].round(1)

    # --- 3. DOWNLOAD DATA PITCHER ---
    print("⏳ [3/4] Mengunduh metrik Pitchers...")
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

    # --- 4. SIMPAN KE CSV ---
    print("⏳ [4/4] Menyimpan ke Database Lokal (CSV)...")
    df_hitters.to_csv('master_hitter_2026.csv', index=False)
    df_pitchers.to_csv('master_pitcher_2026.csv', index=False)
    
    print("✅ PIPELINE SELESAI! AI Model Berhasil di-update.")

if __name__ == "__main__":
    run_pipeline()
