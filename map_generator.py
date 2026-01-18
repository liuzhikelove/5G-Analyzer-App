import pandas as pd
import streamlit as st
import folium
from streamlit_folium import folium_static
import logging
import numpy as np
from functools import lru_cache

# 配置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@st.cache_data
def convert_coords_for_folium(_df):
    """转换坐标为folium使用的WGS84坐标系"""
    if _df is None or _df.empty:
        return pd.DataFrame()
    
    df = _df.copy()
    df['经度'] = pd.to_numeric(df['经度'], errors='coerce')
    df['纬度'] = pd.to_numeric(df['纬度'], errors='coerce')
    df['方位角'] = pd.to_numeric(df['方位角'], errors='coerce')
    df.dropna(subset=['经度', '纬度', '方位角'], inplace=True)
    
    return df

# 缓存装饰器，避免重复计算相同的扇形
@lru_cache(maxsize=10000)
def get_point_at_distance_cached(lon, lat, distance_m, angle_deg):
    """根据距离和角度获取新的坐标，使用缓存避免重复计算"""
    import math
    EARTH_RADIUS = 6378137.0
    
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
    try:
        # 中心点
        center = (lat, lon)
        
        # 计算扇形的起始和结束角度
        start_angle = azimuth - angle_deg / 2
        end_angle = azimuth + angle_deg / 2
        
        # 生成扇形的顶点列表
        sector_points = [center]  # 首先添加中心点
        
        # 生成圆弧上的点
        for i in range(num_points + 1):
            # 计算当前角度
            current_angle = start_angle + (end_angle - start_angle) * (i / num_points)
            # 获取当前角度对应的坐标
            arc_lon, arc_lat = get_point_at_distance(lon, lat, radius_m, current_angle)
            sector_points.append((arc_lat, arc_lon))
        
        # 闭合多边形，添加中心点
        sector_points.append(center)
        
        return sector_points
    except Exception as e:
        logger.error(f"生成扇形失败: {e}")
        # 如果生成扇形失败，返回一个简单的三角形
        return [(lat, lon), (lat + 0.001, lon), (lat, lon + 0.001), (lat, lon)]

def create_sector_shape(lon, lat, azimuth, radius_m, angle_deg=60, num_points=10):
    """包装函数，处理浮点数精度问题后调用缓存函数"""
    try:
        # 限制小数位数，避免因为浮点数精度问题导致缓存失效
        lon_rounded = round(lon, 6)
        lat_rounded = round(lat, 6)
        azimuth_rounded = round(azimuth, 2)
        radius_rounded = round(radius_m)
        angle_rounded = round(angle_deg, 2)
        
        return create_sector_shape_cached(lon_rounded, lat_rounded, azimuth_rounded, radius_rounded, angle_rounded, num_points)
    except Exception as e:
        logger.error(f"创建扇形失败: {e}")
        # 如果创建扇形失败，返回一个简单的三角形
        return [(lat, lon), (lat + 0.001, lon), (lat, lon + 0.001), (lat, lon)]

def create_folium_map(df_4g, df_5g, results_df, baidu_ak, search_name=None):
    """使用folium创建地图，显示小区分布和扇区图"""
    try:
        # 1. 定义颜色映射，确保所有指定的小区类型都有对应的颜色
        color_map = {
            '4G小区': '#336699',            # 蓝色
            '5G小区': '#FF0000',            # 红色
            '共站址5G分流小区': '#28a745',  # 绿色
            '共站址射频调优小区': '#ffc107',  # 黄色
            '非共站址5G分流小区': '#17a2b8',  # 青色
            '需要5G规划建设小区': '#800080',  # 紫色
            '其他': '#6c757d'             # 灰色
        }
        
        # 2. 转换和过滤坐标
        df_4g_conv = convert_coords_for_folium(df_4g)
        df_5g_conv = convert_coords_for_folium(df_5g)
        
        # 3. 初始化地图 - 使用更清晰的OpenStreetMap底图，设置合适的缩放级别
        m = folium.Map(
            location=[22.8170, 108.3661],  # 南宁市中心坐标
            zoom_start=12,
            control_scale=True,
            tiles='OpenStreetMap',  # 使用OpenStreetMap底图，确保能显示清晰的街景
            max_zoom=19  # 设置最大缩放级别为19，这是OpenStreetMap的实际最大缩放级别
        )
        
        # 4. 创建图层 - 按照要求创建所有需要的图层
        layer_4g = folium.FeatureGroup(name="4G小区", show=True)
        layer_5g = folium.FeatureGroup(name="5G小区", show=True)
        layer_colo_offload = folium.FeatureGroup(name="共站址5G分流小区", show=True)
        layer_colo_optimize = folium.FeatureGroup(name="共站址射频调优小区", show=True)
        layer_noncolo_offload = folium.FeatureGroup(name="非共站址5G分流小区", show=True)
        layer_need_construction = folium.FeatureGroup(name="需要5G规划建设小区", show=True)
        
        # 5. 处理5G小区和扇区
        if df_5g_conv is not None and not df_5g_conv.empty:
            for _, row in df_5g_conv.iterrows():
                lon = row['经度']
                lat = row['纬度']
                cell_name = row['小区名称']
                azimuth = row['方位角']
                
                # 生成5G扇区
                try:
                    sector_polygon = create_sector_shape(lon, lat, azimuth, 400, 60, 10)
                    
                    # 添加到5G小区图层
                    folium.Polygon(
                        locations=sector_polygon,
                        color=color_map['5G小区'],
                        fill=True,
                        fill_color=color_map['5G小区'],
                        fill_opacity=0.3,
                        weight=2,
                        opacity=0.8,
                        tooltip=f"5G小区: {cell_name}"
                    ).add_to(layer_5g)
                except Exception as e:
                    logger.error(f"生成5G扇区失败: {e}")
        
        # 6. 处理4G小区和扇区
        # 首先处理没有分析结果的4G小区，确保它们能显示在4G小区图层
        if df_4g_conv is not None and not df_4g_conv.empty:
            for _, row in df_4g_conv.iterrows():
                lon = row['经度']
                lat = row['纬度']
                cell_name = row['小区名称']
                azimuth = row['方位角']
                
                # 生成4G扇区
                try:
                    sector_polygon = create_sector_shape(lon, lat, azimuth, 500, 60, 10)
                    
                    # 直接添加到4G小区图层，确保4G小区能显示
                    folium.Polygon(
                        locations=sector_polygon,
                        color=color_map['4G小区'],
                        fill=True,
                        fill_color=color_map['4G小区'],
                        fill_opacity=0.3,
                        weight=2,
                        opacity=0.8,
                        tooltip=f"4G小区: {cell_name}"
                    ).add_to(layer_4g)
                except Exception as e:
                    logger.error(f"生成4G扇区失败: {e}")
        
        # 7. 处理有分析结果的4G小区，添加到对应的分析结果图层
        df_4g_with_result = pd.DataFrame()
        if df_4g_conv is not None and not df_4g_conv.empty and results_df is not None and not results_df.empty:
            df_4g_with_result = pd.merge(df_4g_conv, results_df[['小区名称', '分析结果']], on='小区名称', how='left')
            
            if not df_4g_with_result.empty:
                for _, row in df_4g_with_result.iterrows():
                    lon = row['经度']
                    lat = row['纬度']
                    cell_name = row['小区名称']
                    azimuth = row['方位角']
                    analysis_result = row['分析结果']
                    analysis_result_str = str(analysis_result)
                    
                    # 生成4G扇区
                    try:
                        sector_polygon = create_sector_shape(lon, lat, azimuth, 500, 60, 10)
                        
                        # 确定小区类别
                        cell_category = '4G小区'
                        
                        # 检查小区类型，确保所有类型都能被正确识别
                        analysis_result_lower = analysis_result_str.lower()
                        
                        # 调整匹配顺序，确保非共站址5G分流小区能被正确识别
                        if '非共站址5G分流小区' in analysis_result_str or '非共站址分流' in analysis_result_lower or '非共站址' in analysis_result_lower:
                            cell_category = '非共站址5G分流小区'
                        elif '共站址射频调优小区' in analysis_result_str or '射频调优' in analysis_result_lower:
                            cell_category = '共站址射频调优小区'
                        elif '共站址5G分流小区' in analysis_result_str or '共站址分流' in analysis_result_lower or '5g分流' in analysis_result_lower:
                            cell_category = '共站址5G分流小区'
                        elif '需要5G规划建设小区' in analysis_result_str or '需要规划' in analysis_result_lower or '规划建设' in analysis_result_lower:
                            cell_category = '需要5G规划建设小区'
                        
                        # 根据类型添加到对应的分析结果图层
                        if cell_category == '共站址5G分流小区':
                            folium.Polygon(
                                locations=sector_polygon,
                                color=color_map['共站址5G分流小区'],
                                fill=True,
                                fill_color=color_map['共站址5G分流小区'],
                                fill_opacity=0.3,
                                weight=2,
                                opacity=0.8,
                                tooltip=f"共站址5G分流小区: {cell_name}<br>分析结果: {analysis_result}"
                            ).add_to(layer_colo_offload)
                        elif cell_category == '共站址射频调优小区':
                            folium.Polygon(
                                locations=sector_polygon,
                                color=color_map['共站址射频调优小区'],
                                fill=True,
                                fill_color=color_map['共站址射频调优小区'],
                                fill_opacity=0.3,
                                weight=2,
                                opacity=0.8,
                                tooltip=f"共站址射频调优小区: {cell_name}<br>分析结果: {analysis_result}"
                            ).add_to(layer_colo_optimize)
                        elif cell_category == '非共站址5G分流小区':
                            folium.Polygon(
                                locations=sector_polygon,
                                color=color_map['非共站址5G分流小区'],
                                fill=True,
                                fill_color=color_map['非共站址5G分流小区'],
                                fill_opacity=0.3,
                                weight=2,
                                opacity=0.8,
                                tooltip=f"非共站址5G分流小区: {cell_name}<br>分析结果: {analysis_result}"
                            ).add_to(layer_noncolo_offload)
                        elif cell_category == '需要5G规划建设小区':
                            folium.Polygon(
                                locations=sector_polygon,
                                color=color_map['需要5G规划建设小区'],
                                fill=True,
                                fill_color=color_map['需要5G规划建设小区'],
                                fill_opacity=0.3,
                                weight=2,
                                opacity=0.8,
                                tooltip=f"需要5G规划建设小区: {cell_name}<br>分析结果: {analysis_result}"
                            ).add_to(layer_need_construction)
                    except Exception as e:
                        logger.error(f"生成分析结果4G扇区失败: {e}")
        
        # 8. 处理搜索功能
        if search_name is not None and search_name.strip():
            # 合并所有小区数据
            all_cells = pd.DataFrame()
            if df_4g_conv is not None and not df_4g_conv.empty:
                all_cells = pd.concat([all_cells, df_4g_conv], ignore_index=True)
            if df_5g_conv is not None and not df_5g_conv.empty:
                all_cells = pd.concat([all_cells, df_5g_conv], ignore_index=True)
            
            if not all_cells.empty:
                # 搜索匹配的小区
                all_cells['小区名称'] = all_cells['小区名称'].astype(str)
                matching_cells = all_cells[all_cells['小区名称'].str.contains(search_name, case=False, na=False)]
                
                if not matching_cells.empty:
                    # 调整地图中心到第一个匹配小区
                    first_match = matching_cells.iloc[0]
                    m.location = [first_match['纬度'], first_match['经度']]
                    m.zoom_start = 15
                    
                    # 添加搜索结果标记
                    for _, match in matching_cells.iterrows():
                        folium.Marker(
                            location=[match['纬度'], match['经度']],
                            icon=folium.Icon(color='purple', icon='star', prefix='fa'),
                            tooltip=f"搜索结果: {match['小区名称']}"
                        ).add_to(m)
        
        # 9. 将所有图层添加到地图，确保LayerControl能正确控制它们
        # 先添加图层，再添加LayerControl和图例
        layer_4g.add_to(m)
        layer_5g.add_to(m)
        layer_colo_offload.add_to(m)
        layer_colo_optimize.add_to(m)
        layer_noncolo_offload.add_to(m)
        layer_need_construction.add_to(m)
        
        # 10. 添加固定图例 - 使用folium.map.CustomControl，将图例固定在左上角
        try:
            # 确保所有图层都有数据，即使是空的也添加一个隐藏的点
            # 这样LayerControl中就能显示所有图层选项
            def ensure_layer_has_data(layer, color):
                if not hasattr(layer, '_children') or len(layer._children) == 0:
                    # 添加一个隐藏的点，确保图层在LayerControl中显示
                    folium.CircleMarker(
                        location=[22.8170, 108.3661],
                        radius=0,
                        color=color,
                        fill=False,
                        opacity=0
                    ).add_to(layer)
            
            # 为每个图层添加隐藏点，确保它们在LayerControl中显示
            ensure_layer_has_data(layer_4g, color_map['4G小区'])
            ensure_layer_has_data(layer_5g, color_map['5G小区'])
            ensure_layer_has_data(layer_colo_offload, color_map['共站址5G分流小区'])
            ensure_layer_has_data(layer_colo_optimize, color_map['共站址射频调优小区'])
            ensure_layer_has_data(layer_noncolo_offload, color_map['非共站址5G分流小区'])
            ensure_layer_has_data(layer_need_construction, color_map['需要5G规划建设小区'])
            
            # 使用简单的HTML字符串创建图例内容
            legend_html = '''
            <div style="background-color: white;
                        border: 2px solid grey;
                        border-radius: 5px;
                        padding: 10px;
                        font-family: Arial, sans-serif;
                        font-size: 12px;">
                <b>图例说明</b><br>
                <div style="display: flex; align-items: center; margin: 5px 0;">
                    <div style="width: 12px; height: 12px; background-color: #336699; margin-right: 8px;"></div>
                    <span>4G小区</span>
                </div>
                <div style="display: flex; align-items: center; margin: 5px 0;">
                    <div style="width: 12px; height: 12px; background-color: #FF0000; margin-right: 8px;"></div>
                    <span>5G小区</span>
                </div>
                <div style="display: flex; align-items: center; margin: 5px 0;">
                    <div style="width: 12px; height: 12px; background-color: #28a745; margin-right: 8px;"></div>
                    <span>共站址5G分流小区</span>
                </div>
                <div style="display: flex; align-items: center; margin: 5px 0;">
                    <div style="width: 12px; height: 12px; background-color: #ffc107; margin-right: 8px;"></div>
                    <span>共站址射频调优小区</span>
                </div>
                <div style="display: flex; align-items: center; margin: 5px 0;">
                    <div style="width: 12px; height: 12px; background-color: #17a2b8; margin-right: 8px;"></div>
                    <span>非共站址5G分流小区</span>
                </div>
                <div style="display: flex; align-items: center; margin: 5px 0;">
                    <div style="width: 12px; height: 12px; background-color: #800080; margin-right: 8px;"></div>
                    <span>需要5G规划建设小区</span>
                </div>
            </div>
            '''
            
            # 使用folium.map.CustomControl添加固定图例，确保图例固定在地图左上角
            from folium.plugins import FloatImage
            from folium.map import CustomControl
            CustomControl(
                html=legend_html,
                position='topleft'
            ).add_to(m)
        except Exception as e:
            logger.error(f"添加图例失败: {e}")
            # 如果添加图例失败，尝试使用Marker+DivIcon作为备选方案
            try:
                folium.Marker(
                    location=[22.8170, 108.3661],
                    icon=folium.DivIcon(
                        html=legend_html,
                        icon_size=(200, None),
                        icon_anchor=(0, 0)
                    ),
                    draggable=False
                ).add_to(m)
            except Exception as e2:
                logger.error(f"备选方案添加图例失败: {e2}")
                pass
        
        # 11. 添加图层控制 - 确保所有图层都能被控制
        # 重新创建LayerControl，确保它能正确控制所有图层
        from folium import LayerControl
        
        # 确保LayerControl在所有图层和图例添加之后添加
        folium.LayerControl(
            position='topright',
            collapsed=False,  # 不折叠，确保用户能看到所有图层选项
            autoZIndex=True  # 自动管理Z轴索引
        ).add_to(m)
        
        # 12. 调整地图中心和缩放级别，确保能看到所有小区
        # 如果有小区数据，调整地图中心到第一个小区
        if df_4g_conv is not None and not df_4g_conv.empty:
            first_cell = df_4g_conv.iloc[0]
            m.location = [first_cell['纬度'], first_cell['经度']]
            m.zoom_start = 10
        elif df_5g_conv is not None and not df_5g_conv.empty:
            first_cell = df_5g_conv.iloc[0]
            m.location = [first_cell['纬度'], first_cell['经度']]
            m.zoom_start = 10
        
        # 12. 返回地图对象
        return m
    except Exception as e:
        logger.error(f"地图生成错误: {str(e)}")
        # 返回一个基本地图，显示错误信息
        m = folium.Map(location=[22.8170, 108.3661], zoom_start=12)
        folium.Marker(
            location=[22.8170, 108.3661],
            icon=folium.Icon(color='red', icon='exclamation-sign'),
            tooltip=f"地图生成错误: {str(e)}"
        ).add_to(m)
        return m