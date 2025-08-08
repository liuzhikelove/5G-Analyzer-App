# ===== File: main_analyzer.py =====

import pandas as pd
from algorithms import calculate_distance, calculate_azimuth_difference

def analyze_5g_offload(df_4g, df_5g, d_colo, theta_colo, d_non_colo, n_non_colo, progress_callback=None):
    """
    根据《计划书》第6页定义的流程图，执行完整的5G分流分析。
    """
    results = []
    total_rows = len(df_4g)

    df_5g[['纬度', '经度', '方位角']] = df_5g[['纬度', '经度', '方位角']].apply(pd.to_numeric, errors='coerce')
    df_5g.dropna(subset=['纬度', '经度', '方位角'], inplace=True)

    for index, row_4g in df_4g.iterrows():
        lat_4g = row_4g.get('纬度')
        lon_4g = row_4g.get('经度')
        azimuth_4g = row_4g.get('方位角')
        
        if pd.isna(lat_4g) or pd.isna(lon_4g) or pd.isna(azimuth_4g):
            current_result = row_4g.to_dict()
            current_result['分析结果'] = "数据缺失(经纬度或方位角)"
            results.append(current_result)
            if progress_callback:
                progress_callback(index + 1, total_rows)
            continue

        distances = [
            (calculate_distance(lat_4g, lon_4g, row_5g['纬度'], row_5g['经度']), row_5g)
            for _, row_5g in df_5g.iterrows()
        ]

        analysis_result = "5G规划建设" 
        nearby_5g_cells = [item for item in distances if item[0] <= d_non_colo]

        if not nearby_5g_cells:
            analysis_result = "5G规划建设"
        else:
            min_dist, nearest_5g_cell = min(nearby_5g_cells, key=lambda x: x[0])
            azimuth_5g = nearest_5g_cell['方位角']
            angle_diff = calculate_azimuth_difference(azimuth_4g, azimuth_5g)

            if min_dist <= d_colo:
                if angle_diff <= theta_colo:
                    analysis_result = f"共站址5G分流小区 (关联小区: {nearest_5g_cell['小区名称']}, 距离: {min_dist:.2f}m, 夹角: {angle_diff:.2f}°)"
                else:
                    analysis_result = f"共站址5G射频调优小区 (关联小区: {nearest_5g_cell['小区名称']}, 距离: {min_dist:.2f}m, 夹角: {angle_diff:.2f}°)"
            else:
                if len(nearby_5g_cells) >= n_non_colo:
                    analysis_result = f"非共站址5G分流小区 (范围内有{len(nearby_5g_cells)}个5G小区，最近距离: {min_dist:.2f}m)"
                else:
                    analysis_result = "5G规划建设"

        current_result = row_4g.to_dict()
        current_result['分析结果'] = analysis_result
        results.append(current_result)
        
        if progress_callback:
            progress_callback(index + 1, total_rows)

    return pd.DataFrame(results)