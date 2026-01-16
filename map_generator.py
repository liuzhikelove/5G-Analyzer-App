# ===== File: map_generator.py (使用folium替代BMap版 v3.0) =====
import pandas as pd
import streamlit as st
import math
from algorithms import create_sector_polygon
import folium
from streamlit_folium import folium_static
import streamlit.components.v1 as components

@st.cache_data
def convert_coords_for_folium(_df):
    """转换坐标为folium使用的WGS84坐标系"""
    df = _df.copy(); 
    if df is None or df.empty: return pd.DataFrame()
    df['经度'] = pd.to_numeric(df['经度'], errors='coerce'); df['纬度'] = pd.to_numeric(df['纬度'], errors='coerce'); df.dropna(subset=['经度', '纬度'], inplace=True)
    if df.empty: return pd.DataFrame()
    
    return df

def create_folium_map(df_4g, df_5g, results_df, baidu_ak, search_name=None):
    """使用folium创建地图"""
    try:
        # 转换坐标（folium使用WGS84坐标，不需要转换为百度坐标系）
        df_4g_conv = convert_coords_for_folium(df_4g); df_5g_conv = convert_coords_for_folium(df_5g)
        if df_4g_conv.empty: return "没有有效的4G数据用于地图显示。"
        
        # 过滤掉可能导致问题的异常坐标
        df_4g_conv = df_4g_conv[(df_4g_conv['经度'] >= 73) & (df_4g_conv['经度'] <= 135) & 
                               (df_4g_conv['纬度'] >= 18) & (df_4g_conv['纬度'] <= 53)]
        df_5g_conv = df_5g_conv[(df_5g_conv['经度'] >= 73) & (df_5g_conv['经度'] <= 135) & 
                               (df_5g_conv['纬度'] >= 18) & (df_5g_conv['纬度'] <= 53)]
        
        if df_4g_conv.empty: return "没有有效的4G数据用于地图显示。"
        
        df_4g_vis = pd.merge(df_4g_conv, results_df[['小区名称', '分析结果']], on='小区名称', how='left')
        categories = {'共站址5G分流小区': [],'共站址5G射频调优小区': [],'非共站址5G分流小区': [],'5G规划建设': [],'其他': []}
        
        # 为每个类别添加数据，确保所有坐标都是有效的
        for _, r in df_4g_vis.iterrows():
            try:
                res = str(r.get('分析结果', '')); matched=False
                lon = r['经度']; lat = r['纬度']
                # 确保坐标是有效数值
                if pd.isna(lon) or pd.isna(lat):
                    continue
                
                # 确保坐标在合理范围内
                if not (73 <= lon <= 135 and 18 <= lat <= 53):
                    continue
                    
                for cat_key in categories.keys():
                    if cat_key in res: categories[cat_key].append([lon, lat]); matched=True; break
                if not matched: categories['其他'].append([lon, lat])
            except Exception as e:
                continue
        
        # 5G站点数据
        g5_stations = []
        if not df_5g_conv.empty:
            for _, r in df_5g_conv.iterrows():
                try:
                    lon = r['经度']
                    lat = r['纬度']
                    
                    # 检查经纬度是否有效
                    if pd.notna(lon) and pd.notna(lat) and isinstance(lon, (int, float)) and isinstance(lat, (int, float)):
                        # 检查经纬度是否在合理范围内
                        if 73 <= lon <= 135 and 18 <= lat <= 53:
                            g5_stations.append([lon, lat])  # 只添加经度和纬度，不添加权重
                except Exception as e:
                    continue
        
        # 计算中心坐标，使用中位数而不是均值，更稳健
        if not df_4g_conv.empty:
            center_lon = df_4g_conv['经度'].median()
            center_lat = df_4g_conv['纬度'].median()
        elif not df_5g_conv.empty:
            center_lon = df_5g_conv['经度'].median()
            center_lat = df_5g_conv['纬度'].median()
        else:
            # 默认中心坐标（南宁市中心）
            center_lon = 108.380886
            center_lat = 22.825828
        
        # 创建地图对象，使用国内可用的高德地图瓦片
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=12,
            control_scale=True,
            prefer_canvas=True,
            tiles=None  # 不使用默认瓦片
        )
        
        # 添加高德地图瓦片图层（国内可用）
        folium.TileLayer(
            name='高德地图',
            tiles='https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
            attr='高德地图',
            subdomains='1234',
            max_zoom=19,
            show=True
        ).add_to(m)
        
        # 颜色映射，调整名称以匹配用户期望
        color_map = {
            '共站址5G分流小区': '#28a745',
            '共站址射频调优小区': '#ffc107',
            '非共站址5G分流小区': '#17a2b8',
            '需要5G规划建设小区': '#dc3545',
            '其他': '#6c757d'
        }
        
        # 显示数据统计信息
        # 添加5G站点标记
        if g5_stations:
            # 创建5G站点图层
            g5_layer = folium.FeatureGroup(name="5G站点", show=True)
            
            # 添加5G站点标记
            for station in g5_stations[:100]:  # 只显示前100个站点
                lon, lat = station
                folium.CircleMarker(
                    location=[lat, lon],
                    radius=5,
                    color='#1f77b4',
                    fill=True,
                    fill_color='#1f77b4',
                    fill_opacity=0.6,
                    tooltip="5G站点"
                ).add_to(g5_layer)
            
            g5_layer.add_to(m)
        
        # 使用实际数据生成扇区图
        import math
        EARTH_RADIUS = 6378137.0
        
        # 使用缓存装饰器，避免重复计算相同的扇形
        from functools import lru_cache
        
        # 计算距离和角度对应的坐标
        @lru_cache(maxsize=10000)
        def get_point_at_distance_cached(lon, lat, distance_m, angle_deg):
            """根据距离和角度获取新的坐标，使用缓存避免重复计算"""
            lon_rad = math.radians(lon)
            lat_rad = math.radians(lat)
            angle_rad = math.radians(angle_deg)
            
            # 计算新的纬度
            new_lat = math.asin(math.sin(lat_rad) * math.cos(distance_m/EARTH_RADIUS) + 
                               math.cos(lat_rad) * math.sin(distance_m/EARTH_RADIUS) * math.cos(angle_rad))
            
            # 计算新的经度
            new_lon = lon_rad + math.atan2(math.sin(angle_rad) * math.sin(distance_m/EARTH_RADIUS) * math.cos(lat_rad),
                                         math.cos(distance_m/EARTH_RADIUS) - math.sin(lat_rad) * math.sin(new_lat))
            
            return math.degrees(new_lon), math.degrees(new_lat)
        
        def get_point_at_distance(lon, lat, distance_m, angle_deg):
            """包装函数，处理浮点数精度问题后调用缓存函数"""
            # 限制小数位数，避免因为浮点数精度问题导致缓存失效
            lon_rounded = round(lon, 6)
            lat_rounded = round(lat, 6)
            distance_rounded = round(distance_m)
            angle_rounded = round(angle_deg, 2)
            
            return get_point_at_distance_cached(lon_rounded, lat_rounded, distance_rounded, angle_rounded)
        
        @lru_cache(maxsize=5000)
        def create_sector_shape_cached(lon, lat, azimuth, radius_m, angle_deg=60, num_points=10):
            """创建真实的扇形形状，通过多个点模拟圆弧边，使用缓存避免重复计算"""
            # 中心点
            center = (lat, lon)
            
            # 计算扇形的起始和结束角度
            start_angle = azimuth - angle_deg / 2
            end_angle = azimuth + angle_deg / 2
            
            # 生成扇形的顶点列表
            sector_points = [center]  # 首先添加中心点
            
            # 生成圆弧上的点，减少点数量以提高性能
            for i in range(num_points + 1):
                # 计算当前角度
                current_angle = start_angle + (end_angle - start_angle) * (i / num_points)
                # 获取当前角度对应的坐标
                arc_lon, arc_lat = get_point_at_distance(lon, lat, radius_m, current_angle)
                sector_points.append((arc_lat, arc_lon))
            
            # 闭合多边形，添加中心点
            sector_points.append(center)
            
            return sector_points
        
        def create_sector_shape(lon, lat, azimuth, radius_m, angle_deg=60, num_points=10):
            """包装函数，处理浮点数精度问题后调用缓存函数"""
            # 限制小数位数，避免因为浮点数精度问题导致缓存失效
            lon_rounded = round(lon, 6)
            lat_rounded = round(lat, 6)
            azimuth_rounded = round(azimuth, 2)
            radius_rounded = round(radius_m)
            angle_rounded = round(angle_deg, 2)
            
            return create_sector_shape_cached(lon_rounded, lat_rounded, azimuth_rounded, radius_rounded, angle_rounded, num_points)
        
        # 1. 处理4G小区扇区 - 根据分析结果使用不同颜色
        if not df_4g_conv.empty:
            # 创建与分析结果对应的图层
            result_layers = {}  
            for category in color_map.keys():
                result_layers[category] = folium.FeatureGroup(name=category, show=True)
            
            # 添加一个单独的4G小区图层选项
            sector_layer_4g = folium.FeatureGroup(name="4G小区", show=True)
            
            # 合并4G数据和分析结果
            df_4g_with_result = pd.merge(df_4g_conv, results_df[['小区名称', '分析结果']], on='小区名称', how='left')
            
            # 使用实际数据生成扇区，根据分析结果使用不同颜色
            for idx, (_, r) in enumerate(df_4g_with_result.iterrows()):
                try:
                    # 获取小区数据
                    lon = r.get('经度', None)
                    lat = r.get('纬度', None)
                    azimuth = r.get('方位角', 0)
                    cell_name = r.get('小区名称', f"4G小区_{idx}")
                    analysis_result = r.get('分析结果', '其他')
                    
                    if pd.notna(lon) and pd.notna(lat):
                        # 确定小区类别
                        cell_category = '其他'
                        
                        # 优先匹配完整的类别名称
                        for category in color_map.keys():
                            if category in analysis_result:
                                cell_category = category
                                break
                        
                        # 特殊情况处理：如果没有匹配到，根据关键词判断
                        if cell_category == '其他':
                            if '共站址' in analysis_result and '射频调优' in analysis_result:
                                cell_category = '共站址射频调优小区'
                            elif '非共站址' in analysis_result and '5G分流' in analysis_result:
                                cell_category = '非共站址5G分流小区'
                            elif '5G规划建设' in analysis_result:
                                cell_category = '需要5G规划建设小区'
                        
                        # 获取对应的颜色
                        cell_color = color_map[cell_category]
                        
                        # 生成真实的扇形形状，使用缓存避免重复计算，缩小半径到500米
                        sector_polygon = create_sector_shape(lon, lat, azimuth, 500, 60, 10)  # 10个点模拟圆弧，平衡性能和视觉效果
                        
                        # 创建扇区多边形对象
                        sector_poly = folium.Polygon(
                            locations=sector_polygon,
                            color=cell_color,
                            fill=True,
                            fill_color=cell_color,
                            fill_opacity=0.5,  # 适当降低透明度，避免遮挡
                            weight=1,  # 减少边框宽度
                            # 放大tooltip字体大小
                            tooltip=folium.Tooltip(
                                f"<div style='font-size: 14px; font-weight: bold;'>{cell_name}</div><div style='font-size: 12px;'>{analysis_result}</div>",
                                sticky=True
                            )
                        )
                        
                        # 添加扇区到对应的结果图层
                        sector_poly.add_to(result_layers[cell_category])
                        # 同时添加到4G小区图层
                        sector_poly.add_to(sector_layer_4g)
                except Exception as e:
                    continue
            
            # 添加4G小区图层到地图
            sector_layer_4g.add_to(m)
            
            # 添加所有结果图层到地图
            for layer in result_layers.values():
                layer.add_to(m)
        
        # 2. 处理5G小区 - 使用实际数据，不限制数量，通过缓存提高性能
        if not df_5g_conv.empty:
            sector_layer_5g = folium.FeatureGroup(name="5G小区扇区", show=True)
            
            # 使用实际数据生成扇区，不限制数量，通过缓存提高性能
            for idx, (_, r) in enumerate(df_5g_conv.iterrows()):
                try:
                    # 获取小区数据
                    lon = r.get('经度', None)
                    lat = r.get('纬度', None)
                    azimuth = r.get('方位角', 0)
                    cell_name = r.get('小区名称', f"5G小区_{idx}")
                    
                    if pd.notna(lon) and pd.notna(lat):
                        # 生成真实的扇形形状，使用缓存避免重复计算，缩小半径到400米
                        sector_polygon = create_sector_shape(lon, lat, azimuth, 400, 60, 10)  # 10个点模拟圆弧，平衡性能和视觉效果
                        
                        # 添加扇区到图层
                        folium.Polygon(
                            locations=sector_polygon,
                            color='#0000FF',  # 蓝色，醒目
                            fill=True,
                            fill_color='#0000FF',
                            fill_opacity=0.5,  # 适当降低透明度
                            weight=1,  # 减少边框宽度
                            # 放大tooltip字体大小
                            tooltip=folium.Tooltip(
                                f"<div style='font-size: 14px; font-weight: bold;'>5G小区: {cell_name}</div><div style='font-size: 12px;'>方位角: {azimuth}°</div>",
                                sticky=True
                            )
                        ).add_to(sector_layer_5g)
                except Exception as e:
                    continue
            
            # 添加5G扇区图层到地图
            sector_layer_5g.add_to(m)
        
        # 3. 确保扇区可见 - 如果没有小区标记，则添加一个默认的扇区
        if 'sector_layer_4g' not in locals() and 'sector_layer_5g' not in locals():
            # 创建一个默认扇区，确保用户能看到扇区效果
            default_lon = center_lon
            default_lat = center_lat
            default_azimuth = 0
            
            # 生成真实的扇形形状
            default_sector = create_sector_shape(default_lon, default_lat, default_azimuth, 1000, 60, 20)
            
            # 添加默认扇区图层
            default_sector_layer = folium.FeatureGroup(name="演示扇区", show=True)
            folium.Polygon(
                locations=default_sector,
                color='#FFFF00',  # 黄色，非常醒目
                fill=True,
                fill_color='#FFFF00',
                fill_opacity=0.8,
                weight=5,
                tooltip=folium.Tooltip("演示扇区<br>点击'开始分析'上传数据查看实际扇区", sticky=True)
            ).add_to(default_sector_layer)
            
            default_sector_layer.add_to(m)
        
        # 确保地图中心指向有扇区的位置
        if not df_4g_conv.empty:
            # 使用第一个4G小区作为地图中心
            first_4g = df_4g_conv.iloc[0]
            m.location = [first_4g['纬度'], first_4g['经度']]
        elif not df_5g_conv.empty:
            # 使用第一个5G小区作为地图中心
            first_5g = df_5g_conv.iloc[0]
            m.location = [first_5g['纬度'], first_5g['经度']]
        
        # 添加小区标记 - 根据分析结果使用不同颜色
        if not df_4g_conv.empty:
            # 合并4G数据和分析结果
            df_4g_with_result = pd.merge(df_4g_conv, results_df[['小区名称', '分析结果']], on='小区名称', how='left')
            
            # 创建小区标记图层
            marker_layer = folium.FeatureGroup(name="小区标记", show=True)
            
            # 添加小区标记，根据分析结果使用不同颜色
            for idx, (_, r) in enumerate(df_4g_with_result.iterrows()):
                try:
                    # 获取小区数据
                    lon = r.get('经度', None)
                    lat = r.get('纬度', None)
                    cell_name = r.get('小区名称', f"4G小区_{idx}")
                    analysis_result = r.get('分析结果', '其他')
                    
                    if pd.notna(lon) and pd.notna(lat):
                        # 确定小区类别
                        cell_category = '其他'
                        
                        # 优先匹配完整的类别名称
                        for category in color_map.keys():
                            if category in analysis_result:
                                cell_category = category
                                break
                        
                        # 特殊情况处理：如果没有匹配到，根据关键词判断
                        if cell_category == '其他':
                            if '共站址' in analysis_result and '射频调优' in analysis_result:
                                cell_category = '共站址射频调优小区'
                            elif '非共站址' in analysis_result and '5G分流' in analysis_result:
                                cell_category = '非共站址5G分流小区'
                            elif '5G规划建设' in analysis_result:
                                cell_category = '需要5G规划建设小区'
                        
                        # 获取对应的颜色
                        cell_color = color_map[cell_category]
                        
                        # 将颜色转换为folium图标支持的颜色名称
                        folium_color = 'red'  # 默认颜色
                        if cell_color == '#28a745':  # 绿色
                            folium_color = 'green'
                        elif cell_color == '#ffc107':  # 黄色
                            folium_color = 'orange'
                        elif cell_color == '#17a2b8':  # 蓝色
                            folium_color = 'blue'
                        elif cell_color == '#dc3545':  # 红色
                            folium_color = 'red'
                        
                        # 添加标记到图层
                        folium.Marker(
                            location=[lat, lon],
                            icon=folium.Icon(color=folium_color, icon='info-sign'),
                            # 放大tooltip字体大小
                            tooltip=folium.Tooltip(
                                f"<div style='font-size: 14px; font-weight: bold;'>{cell_name}</div><div style='font-size: 12px;'>{analysis_result}</div>",
                                sticky=True
                            )
                        ).add_to(marker_layer)
                except Exception as e:
                    continue
            
            # 添加小区标记图层到地图
            marker_layer.add_to(m)
        
        # 添加热力图
        if not df_4g_vis.empty:
            heatmap_data = []
            for _, r in df_4g_vis.iterrows():
                try:
                    lon = r['经度']
                    lat = r['纬度']
                    if pd.notna(lon) and pd.notna(lat):
                        heatmap_data.append([lat, lon])
                except Exception as e:
                    continue
            
            if heatmap_data:
                # 创建热力图图层
                heat_layer = folium.FeatureGroup(name="小区热力图", show=False)
                from folium.plugins import HeatMap
                HeatMap(heatmap_data, radius=15, blur=10).add_to(heat_layer)
                heat_layer.add_to(m)
        
        # 添加标题
        folium.map.Marker(
            [center_lat, center_lon],
            icon=folium.DivIcon(
                icon_size=(200,36),
                icon_anchor=(0,0),
                html=f'<div style="font-size:16pt; font-weight:bold; text-align:center;">小区分析结果地图可视化</div>',
            )
        ).add_to(m)
        
        # 处理搜索结果定位
        search_results = []
        if search_name is not None and search_name.strip():
            # 直接在转换后的4G和5G数据中搜索，确保搜索结果能够显示
            all_cells = pd.concat([df_4g_conv, df_5g_conv], ignore_index=True) if not df_4g_conv.empty or not df_5g_conv.empty else pd.DataFrame()
            
            # 在转换后的有效数据上搜索
            matching_cells = all_cells[all_cells['小区名称'].str.contains(search_name, case=False, na=False)] if not all_cells.empty else pd.DataFrame()
            
            # 如果在有效数据中没有找到，再尝试在原始数据中搜索
            if matching_cells.empty:
                # 合并原始数据进行搜索
                original_4g = df_4g.copy() if df_4g is not None else pd.DataFrame()
                original_5g = df_5g.copy() if df_5g is not None else pd.DataFrame()
                
                # 清理原始数据的小区名称列
                if not original_4g.empty:
                    original_4g['小区名称'] = original_4g['小区名称'].astype(str)
                if not original_5g.empty:
                    original_5g['小区名称'] = original_5g['小区名称'].astype(str)
                
                all_original_cells = pd.concat([original_4g, original_5g], ignore_index=True)
                matching_original_cells = all_original_cells[all_original_cells['小区名称'].str.contains(search_name, case=False, na=False)] if not all_original_cells.empty else pd.DataFrame()
                
                if not matching_original_cells.empty:
                    # 直接在地图上添加原始数据的标记
                    for _, original_cell in matching_original_cells.iterrows():
                        try:
                            # 获取原始数据的坐标
                            cell_name = original_cell['小区名称']
                            cell_lat = float(original_cell['纬度']) if pd.notna(original_cell['纬度']) else None
                            cell_lon = float(original_cell['经度']) if pd.notna(original_cell['经度']) else None
                            
                            if cell_lat is not None and cell_lon is not None:
                                # 调整地图中心到该小区
                                m.location = [cell_lat, cell_lon]
                                m.zoom_start = 18
                                
                                # 添加醒目的标记
                                folium.Marker(
                                    location=[cell_lat, cell_lon],
                                    icon=folium.Icon(color='yellow', icon='star', prefix='fa', icon_color='black'),
                                    tooltip=folium.Tooltip(
                                        f"<div style='font-size: 16px; font-weight: bold; color: yellow;'>搜索结果: {cell_name}</div><div style='font-size: 14px;'>经度: {cell_lon:.6f}<br>纬度: {cell_lat:.6f}</div><div style='font-size: 12px;'>注意: 该小区可能不在有效数据中</div>",
                                        sticky=True
                                    )
                                ).add_to(m)
                                
                                # 添加更大的黄色圆圈标记
                                folium.Circle(
                                    location=[cell_lat, cell_lon],
                                    radius=300,
                                    color='yellow',
                                    fill=True,
                                    fill_color='yellow',
                                    fill_opacity=0.4,
                                    weight=4
                                ).add_to(m)
                        except Exception as e:
                            pass
                else:
                    # 搜索结果为空，添加一个提示标记
                    folium.Marker(
                        location=m.location,
                        icon=folium.Icon(color='red', icon='exclamation-sign', prefix='fa'),
                        tooltip=folium.Tooltip(
                            f"<div style='font-size: 16px; font-weight: bold; color: red;'>未找到匹配的小区</div><div style='font-size: 14px;'>搜索关键词: {search_name}</div><div style='font-size: 12px;'>请检查小区名称拼写是否正确</div>",
                            sticky=True
                        )
                    ).add_to(m)
            else:
                # 显示所有匹配的小区
                for idx, (_, search_result) in enumerate(matching_cells.iterrows()):
                    # 获取搜索结果的经纬度
                    search_lat = search_result['纬度']
                    search_lon = search_result['经度']
                    search_cell_name = search_result['小区名称']
                    
                    # 对于第一个匹配的小区，调整地图中心
                    if idx == 0:
                        m.location = [search_lat, search_lon]
                        m.zoom_start = 18  # 放大到更大级别，确保用户能看到
                    
                    # 添加搜索结果标记 - 使用最醒目的颜色和图标
                    folium.Marker(
                        location=[search_lat, search_lon],
                        icon=folium.Icon(color='red', icon='flag', prefix='fa', icon_color='white'),  # 使用红色旗帜标记，非常醒目
                        tooltip=folium.Tooltip(
                            f"<div style='font-size: 16px; font-weight: bold; color: red;'>搜索结果: {search_cell_name}</div><div style='font-size: 14px;'>经度: {search_lon:.6f}<br>纬度: {search_lat:.6f}</div>",
                            sticky=True
                        )
                    ).add_to(m)
                    
                    # 添加一个更大的红色圆圈标记，非常醒目
                    folium.Circle(
                        location=[search_lat, search_lon],
                        radius=300,  # 300米半径，更大更醒目
                        color='red',
                        fill=True,
                        fill_color='red',
                        fill_opacity=0.4,
                        weight=4
                    ).add_to(m)
                    
                    # 添加一个非常醒目的红色圆形标记
                    folium.CircleMarker(
                        location=[search_lat, search_lon],
                        radius=20,
                        color='red',
                        fill=True,
                        fill_color='red',
                        fill_opacity=0.9
                    ).add_to(m)
                    
                    # 添加一个蓝色的脉冲标记，增加视觉效果
                    folium.CircleMarker(
                        location=[search_lat, search_lon],
                        radius=10,
                        color='blue',
                        fill=True,
                        fill_color='blue',
                        fill_opacity=0.7
                    ).add_to(m)
        
        # 添加自定义图例
        legend_html = '''
        <div style="position: fixed; 
                    top: 50px; left: 50px; width: 200px; height: auto; 
                    background-color: white; z-index:9999; 
                    border: 2px solid grey; padding: 10px; 
                    font-size: 14px;">
            <h4 style="margin-top: 0; text-align: center;">图例说明</h4>
        '''
        
        for name, color in color_map.items():
            if name != '其他':  # 只显示主要类别
                legend_html += f'''<div style="margin: 5px 0;">
                    <div style="display: inline-block; width: 20px; height: 20px; 
                                background-color: {color}; margin-right: 10px; 
                                border: 1px solid #333;"></div>
                    <span>{name}</span>
                </div>'''
        
        legend_html += '''</div>'''
        
        m.get_root().html.add_child(folium.Element(legend_html))
        
        # 添加图层控制
        folium.LayerControl().add_to(m)
        
        # 使用iframe方式显示地图，确保底图正确加载
        import tempfile
        import os
        
        # 保存地图为HTML文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            m.save(f.name)
            map_path = f.name
        
        # 使用Streamlit的iframe组件显示地图
        with open(map_path, 'r', encoding='utf-8') as f:
            map_html = f.read()
        
        # 显示地图
        components.html(map_html, width=1600, height=1200, scrolling=False)
        
        # 删除临时文件
        os.unlink(map_path)
        
        return None
    except Exception as e:
        return f"地图生成过程中出错：{str(e)}"