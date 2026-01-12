# ===== File: main_analyzer.py (最终高性能版 v4.0) =====
import pandas as pd
import numpy as np
# 简化导入，只导入必要的模块
from algorithms import calculate_distance, calculate_azimuth_difference

# 尝试导入 scipy，如果失败则使用替代方案
try:
    from scipy.spatial import cKDTree
except ImportError:
    # 如果 scipy 不可用，使用简单的距离计算替代
    pass
DEGREE_PER_METER = 1 / 111320
def analyze_5g_offload(df_4g, df_5g, d_colo, theta_colo, d_non_colo, n_non_colo, progress_callback=None):
    results = []
    
    # 转换数值类型并过滤无效数据
    for col in ['经度', '纬度', '方位角']:
        df_4g[col] = pd.to_numeric(df_4g[col], errors='coerce')
        df_5g[col] = pd.to_numeric(df_5g[col], errors='coerce')
    
    df_4g.dropna(subset=['经度', '纬度', '方位角'], inplace=True)
    df_5g.dropna(subset=['经度', '纬度', '方位角'], inplace=True)
    
    total_rows = len(df_4g)
    
    # 处理5G数据为空的情况
    if df_5g.empty:
        for idx, (_, row_4g) in enumerate(df_4g.iterrows()):
            current_result = row_4g.to_dict()
            current_result['分析结果'] = "5G规划建设"
            current_result['建议分流小区'] = "N/A"
            results.append(current_result)
            if progress_callback:
                progress_callback(idx + 1, total_rows)
        return pd.DataFrame(results)
    
    # 获取5G小区坐标
    coords_5g = df_5g[['纬度', '经度']].values
    
    # 根据是否有cKDTree选择不同的近邻搜索方法
    if 'cKDTree' in globals():
        # 使用scipy的cKDTree进行高效搜索
        tree_5g = cKDTree(coords_5g)
        radius_in_degrees = d_non_colo * DEGREE_PER_METER
        
        for idx, (_, row_4g) in enumerate(df_4g.iterrows()):
            lat_4g = row_4g['纬度']
            lon_4g = row_4g['经度']
            azimuth_4g = row_4g['方位角']
            coord_4g = [lat_4g, lon_4g]
            
            # 使用KDTree查找附近的5G小区
            nearby_indices = tree_5g.query_ball_point(coord_4g, r=radius_in_degrees)
            
            analysis_result = "5G规划建设"
            suggested_cell_name = "N/A"
            
            if nearby_indices:
                df_nearby_5g = df_5g.iloc[nearby_indices]
                distances = []
                
                # 计算距离
                for _, row_5g in df_nearby_5g.iterrows():
                    dist = calculate_distance(lat_4g, lon_4g, row_5g['纬度'], row_5g['经度'])
                    distances.append((dist, row_5g))
                
                min_dist, nearest_5g_cell = min(distances, key=lambda x: x[0])
                azimuth_5g = nearest_5g_cell['方位角']
                angle_diff = calculate_azimuth_difference(azimuth_4g, azimuth_5g)
                
                # 共站址判断
                if min_dist <= d_colo:
                    suggested_cell_name = nearest_5g_cell['小区名称']
                    if angle_diff <= theta_colo:
                        analysis_result = f"共站址5G分流小区 (关联小区: {suggested_cell_name}, 距离: {min_dist:.2f}m, 夹角: {angle_diff:.2f}°)"
                    else:
                        analysis_result = f"共站址5G射频调优小区 (关联小区: {suggested_cell_name}, 距离: {min_dist:.2f}m, 夹角: {angle_diff:.2f}°)"
                elif min_dist <= d_non_colo:
                    # 非共站址判断
                    if len(nearby_indices) >= n_non_colo:
                        suggested_cell_name = nearest_5g_cell['小区名称']
                        analysis_result = f"非共站址5G分流小区 (范围内有{len(nearby_indices)}个5G小区，最近距离: {min_dist:.2f}m)"
            
            # 保存结果
            current_result = row_4g.to_dict()
            current_result['分析结果'] = analysis_result
            current_result['建议分流小区'] = suggested_cell_name
            results.append(current_result)
            
            if progress_callback:
                progress_callback(idx + 1, total_rows)
    else:
        # 不使用cKDTree，直接计算距离（适合小数据集）
        for idx, (_, row_4g) in enumerate(df_4g.iterrows()):
            lat_4g = row_4g['纬度']
            lon_4g = row_4g['经度']
            azimuth_4g = row_4g['方位角']
            
            nearby_5g_cells = []
            for _, row_5g in df_5g.iterrows():
                dist = calculate_distance(lat_4g, lon_4g, row_5g['纬度'], row_5g['经度'])
                if dist <= d_non_colo:
                    nearby_5g_cells.append((dist, row_5g))
            
            analysis_result = "5G规划建设"
            suggested_cell_name = "N/A"
            
            if nearby_5g_cells:
                min_dist, nearest_5g_cell = min(nearby_5g_cells, key=lambda x: x[0])
                azimuth_5g = nearest_5g_cell['方位角']
                angle_diff = calculate_azimuth_difference(azimuth_4g, azimuth_5g)
                
                # 共站址判断
                if min_dist <= d_colo:
                    suggested_cell_name = nearest_5g_cell['小区名称']
                    if angle_diff <= theta_colo:
                        analysis_result = f"共站址5G分流小区 (关联小区: {suggested_cell_name}, 距离: {min_dist:.2f}m, 夹角: {angle_diff:.2f}°)"
                    else:
                        analysis_result = f"共站址5G射频调优小区 (关联小区: {suggested_cell_name}, 距离: {min_dist:.2f}m, 夹角: {angle_diff:.2f}°)"
                # 非共站址判断
                elif len(nearby_5g_cells) >= n_non_colo:
                    suggested_cell_name = nearest_5g_cell['小区名称']
                    analysis_result = f"非共站址5G分流小区 (范围内有{len(nearby_5g_cells)}个5G小区，最近距离: {min_dist:.2f}m)"
            
            # 保存结果
            current_result = row_4g.to_dict()
            current_result['分析结果'] = analysis_result
            current_result['建议分流小区'] = suggested_cell_name
            results.append(current_result)
            
            if progress_callback:
                progress_callback(idx + 1, total_rows)
    
    return pd.DataFrame(results)
