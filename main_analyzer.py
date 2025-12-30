# ===== File: main_analyzer.py (最终高性能版 v4.0) =====
import pandas as pd; import numpy as np; from scipy.spatial import cKDTree
from algorithms import calculate_distance, calculate_azimuth_difference
DEGREE_PER_METER = 1 / 111320
def analyze_5g_offload(df_4g, df_5g, d_colo, theta_colo, d_non_colo, n_non_colo, progress_callback=None):
    results = []; total_rows = len(df_4g)
    for col in ['经度', '纬度', '方位角']: df_4g[col] = pd.to_numeric(df_4g[col], errors='coerce'); df_5g[col] = pd.to_numeric(df_5g[col], errors='coerce')
    df_4g.dropna(subset=['经度', '纬度', '方位角'], inplace=True); df_5g.dropna(subset=['经度', '纬度', '方位角'], inplace=True)
    if df_5g.empty:
        for _, row_4g in df_4g.iterrows():
            current_result = row_4g.to_dict(); current_result['分析结果'] = "5G规划建设"; current_result['建议分流小区'] = "N/A"; results.append(current_result)
        return pd.DataFrame(results)
    coords_5g = np.array(df_5g[['纬度', '经度']]); tree_5g = cKDTree(coords_5g); radius_in_degrees = d_non_colo * DEGREE_PER_METER
    for index, row_4g in df_4g.iterrows():
        lat_4g = row_4g['纬度']; lon_4g = row_4g['经度']; azimuth_4g = row_4g['方位角']; coord_4g = [lat_4g, lon_4g]
        nearby_indices = tree_5g.query_ball_point(coord_4g, r=radius_in_degrees)
        analysis_result = "5G规划建设"; suggested_cell_name = "N/A"
        if nearby_indices:
            df_nearby_5g = df_5g.iloc[nearby_indices]; distances = []
            for _, row_5g in df_nearby_5g.iterrows(): distances.append((calculate_distance(lat_4g, lon_4g, row_5g['纬度'], row_5g['经度']), row_5g))
            min_dist, nearest_5g_cell = min(distances, key=lambda x: x[0]); azimuth_5g = nearest_5g_cell['方位角']; angle_diff = calculate_azimuth_difference(azimuth_4g, azimuth_5g)
            if min_dist <= d_colo:
                suggested_cell_name = nearest_5g_cell['小区名称']
                if angle_diff <= theta_colo: analysis_result = f"共站址5G分流小区 (关联小区: {suggested_cell_name}, 距离: {min_dist:.2f}m, 夹角: {angle_diff:.2f}°)"
                else: analysis_result = f"共站址5G射频调优小区 (关联小区: {suggested_cell_name}, 距离: {min_dist:.2f}m, 夹角: {angle_diff:.2f}°)"
            elif min_dist <= d_non_colo:
                if len(nearby_indices) >= n_non_colo: suggested_cell_name = nearest_5g_cell['小区名称']; analysis_result = f"非共站址5G分流小区 (范围内有{len(nearby_indices)}个5G小区，最近距离: {min_dist:.2f}m)"
        current_result = row_4g.to_dict(); current_result['分析结果'] = analysis_result; current_result['建议分流小区'] = suggested_cell_name; results.append(current_result)
        if progress_callback: progress_callback(index + 1, total_rows)
    return pd.DataFrame(results)