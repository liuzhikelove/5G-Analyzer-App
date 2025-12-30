# ===== File: main_analyzer.py (版本 4.0 - 高性能版) =====

import pandas as pd
import numpy as np
from scipy.spatial import cKDTree # 导入 cKDTree 空间索引库
from algorithms import calculate_distance, calculate_azimuth_difference

# --- 核心性能优化：将米转换为近似的经纬度差值 ---
# 地球赤道半径约为 6378137 米, 1度约等于 111.32 公里
DEGREE_PER_METER = 1 / 111320

def analyze_5g_offload(df_4g, df_5g, d_colo, theta_colo, d_non_colo, n_non_colo, progress_callback=None):
    """
    V4.0更新:
    - 使用 SciPy cKDTree 空间索引进行近邻搜索，极大提升大规模数据处理性能。
    """
    results = []
    total_rows = len(df_4g)

    # --- 1. 数据预处理 ---
    # 确保关键列是数值类型，并删除无效行
    for col in ['经度', '纬度', '方位角']:
        df_4g[col] = pd.to_numeric(df_4g[col], errors='coerce')
        df_5g[col] = pd.to_numeric(df_5g[col], errors='coerce')
    df_4g.dropna(subset=['经度', '纬度', '方位角'], inplace=True)
    df_5g.dropna(subset=['经度', '纬度', '方位角'], inplace=True)

    if df_5g.empty: # 如果没有5G数据，直接返回
        for _, row_4g in df_4g.iterrows():
            current_result = row_4g.to_dict()
            current_result['分析结果'] = "5G规划建设"
            current_result['建议分流小区'] = "N/A"
            results.append(current_result)
        return pd.DataFrame(results)

    # --- 2. [核心性能优化] 创建5G小区的空间索引 (cKDTree) ---
    # cKDTree需要一个Nx2的坐标数组
    coords_5g = np.array(df_5g[['纬度', '经度']])
    tree_5g = cKDTree(coords_5g)
    
    # 将搜索半径从米转换为度，用于cKDTree查询
    radius_in_degrees = d_non_colo * DEGREE_PER_METER

    # --- 3. 遍历4G小区并使用空间索引进行高效查询 ---
    for index, row_4g in df_4g.iterrows():
        lat_4g = row_4g['纬度']
        lon_4g = row_4g['经度']
        azimuth_4g = row_4g['方位角']
        
        coord_4g = [lat_4g, lon_4g]
        
        # [核心性能优化] 查询索引树，找到在 d_non_colo 半径内的所有5G小区的索引
        nearby_indices = tree_5g.query_ball_point(coord_4g, r=radius_in_degrees)
        
        analysis_result = "5G规划建设"
        suggested_cell_name = "N/A"

        if nearby_indices: # 如果找到了附近的5G小区
            # 从原始5G DataFrame中筛选出这些附近的小区
            df_nearby_5g = df_5g.iloc[nearby_indices]
            
            # 在这个小得多的子集中计算精确距离
            distances = []
            for _, row_5g in df_nearby_5g.iterrows():
                dist = calculate_distance(lat_4g, lon_4g, row_5g['纬度'], row_5g['经度'])
                distances.append((dist, row_5g))

            # 找到最近的那个5G小区
            min_dist, nearest_5g_cell = min(distances, key=lambda x: x[0])
            azimuth_5g = nearest_5g_cell['方位角']
            angle_diff = calculate_azimuth_difference(azimuth_4g, azimuth_5g)

            if min_dist <= d_colo:
                suggested_cell_name = nearest_5g_cell['小区名称']
                if angle_diff <= theta_colo:
                    analysis_result = f"共站址5G分流小区 (关联小区: {suggested_cell_name}, 距离: {min_dist:.2f}m, 夹角: {angle_diff:.2f}°)"
                else:
                    analysis_result = f"共站址5G射频调优小区 (关联小区: {suggested_cell_name}, 距离: {min_dist:.2f}m, 夹角: {angle_diff:.2f}°)"
            elif min_dist <= d_non_colo: # 确保距离仍在非共站址半径内
                if len(nearby_indices) >= n_non_colo:
                    suggested_cell_name = nearest_5g_cell['小区名称']
                    analysis_result = f"非共站址5G分流小区 (范围内有{len(nearby_indices)}个5G小区，最近距离: {min_dist:.2f}m)"

        current_result = row_4g.to_dict()
        current_result['分析结果'] = analysis_result
        current_result['建议分流小区'] = suggested_cell_name
        results.append(current_result)
        
        if progress_callback: progress_callback(index + 1, total_rows)

    return pd.DataFrame(results)
