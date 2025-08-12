# ===== File: main_analyzer.py (版本 3.1) =====

import pandas as pd
from algorithms import calculate_distance, calculate_azimuth_difference

def analyze_5g_offload(df_4g, df_5g, d_colo, theta_colo, d_non_colo, n_non_colo, progress_callback=None):
    """
    根据《计划书》第6页定义的流程图，执行完整的5G分流分析。
    V3.1更新:
    - [BUG修复] 修正了方位角夹角计算的错误。
    - [功能增加] 增加了“建议分流小区”列的输出。
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
            current_result['建议分流小区'] = "N/A" # 新增列
            results.append(current_result)
            if progress_callback: progress_callback(index + 1, total_rows)
            continue

        distances = [(calculate_distance(lat_4g, lon_4g, r_5g['纬度'], r_5g['经度']), r_5g) for _, r_5g in df_5g.iterrows()]
        
        analysis_result = "5G规划建设" 
        suggested_cell_name = "N/A" # 新增列：默认为N/A
        
        nearby_5g_cells = [item for item in distances if item[0] <= d_non_colo]

        if nearby_5g_cells:
            min_dist, nearest_5g_cell = min(nearby_5g_cells, key=lambda x: x[0])
            azimuth_5g = nearest_5g_cell['方位角']
            
            # --- [BUG修复] 修正这里的第二个参数 ---
            angle_diff = calculate_azimuth_difference(azimuth_4g, azimuth_5g)

            if min_dist <= d_colo:
                # --- [新增] 确定了关联小区，赋值给新变量 ---
                suggested_cell_name = nearest_5g_cell['小区名称']
                if angle_diff <= theta_colo:
                    analysis_result = f"共站址5G分流小区 (关联小区: {suggested_cell_name}, 距离: {min_dist:.2f}m, 夹角: {angle_diff:.2f}°)"
                else:
                    analysis_result = f"共站址5G射频调优小区 (关联小区: {suggested_cell_name}, 距离: {min_dist:.2f}m, 夹角: {angle_diff:.2f}°)"
            else:
                if len(nearby_5g_cells) >= n_non_colo:
                    # --- [新增] 确定了关联小区，赋值给新变量 ---
                    suggested_cell_name = nearest_5g_cell['小区名称']
                    analysis_result = f"非共站址5G分流小区 (范围内有{len(nearby_5g_cells)}个5G小区，最近距离: {min_dist:.2f}m)"

        current_result = row_4g.to_dict()
        current_result['分析结果'] = analysis_result
        current_result['建议分流小区'] = suggested_cell_name # 新增列：加入到结果中
        results.append(current_result)
        
        if progress_callback: progress_callback(index + 1, total_rows)

    return pd.DataFrame(results)