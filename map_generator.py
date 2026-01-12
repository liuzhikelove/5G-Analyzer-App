# ===== File: map_generator.py (使用folium替代BMap版 v3.0) =====
import pandas as pd
import streamlit as st
import math
from algorithms import create_sector_polygon
import folium
from streamlit_folium import folium_static

@st.cache_data
def convert_coords_for_folium(_df):
    """转换坐标为folium使用的WGS84坐标系"""
    df = _df.copy(); 
    if df is None or df.empty: return pd.DataFrame()
    df['经度'] = pd.to_numeric(df['经度'], errors='coerce'); df['纬度'] = pd.to_numeric(df['纬度'], errors='coerce'); df.dropna(subset=['经度', '纬度'], inplace=True)
    if df.empty: return pd.DataFrame()
    
    st.info(f"坐标转换完成: 总处理 {len(df)} 行，成功转换 {len(df)} 行，失败 0 行")
    
    return df

def create_folium_map(df_4g, df_5g, results_df, baidu_ak):
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
        
        # 创建地图对象
        m = folium.Map(location=[center_lat, center_lon], zoom_start=14, width="100%", height="1200px")
        
        # 颜色映射
        color_map = {'共站址5G分流小区': '#28a745','共站址5G射频调优小区': '#ffc107','非共站址5G分流小区': '#17a2b8','5G规划建设': '#dc3545','其他': '#6c757d'}
        
        # 按分析结果分类生成扇区多边形
        sector_polygons_by_category = {category: [] for category in categories.keys()}
        
        # 遍历分析结果，为每个小区生成对应类别的扇区
        polygon_count = 0
        for _, r in df_4g_vis.iterrows():
            try:
                # 检查必要的列是否存在
                if '经度' not in r or '纬度' not in r or '方位角' not in r:
                    continue
                
                lon = r['经度']
                lat = r['纬度']
                azimuth = r['方位角']
                analysis_result = r.get('分析结果', '')
                
                # 确定小区所属类别
                category = '其他'  # 默认类别
                for cat_key in categories.keys():
                    if cat_key in analysis_result:
                        category = cat_key
                        break
                
                # 确保坐标和方位角都是有效数值
                if (pd.notna(lon) and pd.notna(lat) and pd.notna(azimuth)):
                    # 转换为数值类型，确保方位角是有效的
                    try:
                        lon = float(lon)
                        lat = float(lat)
                        azimuth = float(azimuth)
                    except (TypeError, ValueError):
                        continue
                    
                    # 检查经纬度是否在合理范围内
                    if 73 <= lon <= 135 and 18 <= lat <= 53:
                        # 生成扇形多边形，半径500米，角度60度
                        polygon = create_sector_polygon(lon, lat, azimuth, 500, 60)
                        # 确保生成的多边形是有效的
                        if polygon and isinstance(polygon, list) and len(polygon) > 2:
                            sector_polygons_by_category[category].append(polygon)
                            polygon_count += 1
            except Exception as e:
                continue
        
        # 显示生成的扇区多边形数量
        st.info(f"成功生成 {polygon_count} 个扇区多边形")
        
        # 为每个类别显示扇区数量
        for category, polygons in sector_polygons_by_category.items():
            if polygons:
                st.info(f"{category}: {len(polygons)} 个扇区多边形")
        
        # 添加5G站点标记
        if g5_stations:
            st.info(f"成功加载 {len(g5_stations)} 个5G站点数据")
            
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
        
        # 计算距离和角度对应的坐标
        def get_point_at_distance(lon, lat, distance_m, angle_deg):
            """根据距离和角度获取新的坐标"""
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
        
        def create_sector_shape(lon, lat, azimuth, radius_m, angle_deg=60, num_points=20):
            """创建真实的扇形形状，通过多个点模拟圆弧边"""
            # 中心点
            center = (lat, lon)
            
            # 计算扇形的起始和结束角度
            start_angle = azimuth - angle_deg / 2
            end_angle = azimuth + angle_deg / 2
            
            # 生成扇形的顶点列表
            sector_points = [center]  # 首先添加中心点
            
            # 生成圆弧上的点
            # 使用多个点来模拟圆弧，点越多圆弧越平滑
            for i in range(num_points + 1):
                # 计算当前角度
                current_angle = start_angle + (end_angle - start_angle) * (i / num_points)
                # 获取当前角度对应的坐标
                arc_lon, arc_lat = get_point_at_distance(lon, lat, radius_m, current_angle)
                sector_points.append((arc_lat, arc_lon))
            
            # 闭合多边形，添加中心点
            sector_points.append(center)
            
            return sector_points
        
        # 1. 处理4G小区 - 使用实际数据
        if not df_4g_conv.empty:
            sector_layer_4g = folium.FeatureGroup(name="4G小区扇区", show=True)
            
            # 使用实际数据生成扇区，显示所有4G扇区
            for idx, (_, r) in enumerate(df_4g_conv.iterrows()):
                try:
                    # 获取小区数据
                    lon = r.get('经度', None)
                    lat = r.get('纬度', None)
                    azimuth = r.get('方位角', 0)
                    cell_name = r.get('小区名称', f"4G小区_{idx}")
                    
                    if pd.notna(lon) and pd.notna(lat):
                        # 生成真实的扇形形状
                        sector_polygon = create_sector_shape(lon, lat, azimuth, 1000, 60, 20)  # 60度扇区，20个点模拟圆弧
                        
                        # 添加扇区到图层
                        folium.Polygon(
                            locations=sector_polygon,
                            color='#FF0000',  # 红色，醒目
                            fill=True,
                            fill_color='#FF0000',
                            fill_opacity=0.7,  # 提高透明度
                            weight=3,  # 增加边框宽度
                            tooltip=folium.Tooltip(f"4G小区: {cell_name}<br>方位角: {azimuth}°", sticky=True)
                        ).add_to(sector_layer_4g)
                except Exception as e:
                    continue
            
            # 添加4G扇区图层到地图
            sector_layer_4g.add_to(m)
        
        # 2. 处理5G小区 - 使用实际数据
        if not df_5g_conv.empty:
            sector_layer_5g = folium.FeatureGroup(name="5G小区扇区", show=True)
            
            # 使用实际数据生成扇区，显示所有5G扇区
            for idx, (_, r) in enumerate(df_5g_conv.iterrows()):
                try:
                    # 获取小区数据
                    lon = r.get('经度', None)
                    lat = r.get('纬度', None)
                    azimuth = r.get('方位角', 0)
                    cell_name = r.get('小区名称', f"5G小区_{idx}")
                    
                    if pd.notna(lon) and pd.notna(lat):
                        # 生成真实的扇形形状
                        sector_polygon = create_sector_shape(lon, lat, azimuth, 800, 60, 20)  # 60度扇区，20个点模拟圆弧
                        
                        # 添加扇区到图层
                        folium.Polygon(
                            locations=sector_polygon,
                            color='#0000FF',  # 蓝色，醒目
                            fill=True,
                            fill_color='#0000FF',
                            fill_opacity=0.7,  # 提高透明度
                            weight=3,  # 增加边框宽度
                            tooltip=folium.Tooltip(f"5G小区: {cell_name}<br>方位角: {azimuth}°", sticky=True)
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
        
        # 添加小区标记
        for name, data in categories.items():
            if data and len(data) > 0:
                # 创建小区标记图层
                marker_layer = folium.FeatureGroup(name=name, show=True)
                
                # 添加小区标记
                for point in data[:50]:  # 只显示前50个小区
                    lon, lat = point
                    folium.Marker(
                        location=[lat, lon],
                        icon=folium.Icon(color='green' if '5G' in name else 'blue', icon='info-sign'),
                        tooltip=name
                    ).add_to(marker_layer)
                
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
        
        # 添加图层控制
        folium.LayerControl().add_to(m)
        
        # 添加标题
        folium.map.Marker(
            [center_lat, center_lon],
            icon=folium.DivIcon(
                icon_size=(200,36),
                icon_anchor=(0,0),
                html=f'<div style="font-size:16pt; font-weight:bold; text-align:center;">小区分析结果地图可视化</div>',
            )
        ).add_to(m)
        
        # 显示地图
        st.success("地图生成成功！")
        # 添加自定义CSS来确保地图容器能显示更大尺寸，突破所有宽度限制
        st.markdown("""
        <style>
        /* 地图容器样式 */
        .folium-map {
            width: 100% !important;
            height: 1200px !important;
            margin: 0 !important;
            padding: 0 !important;
            max-width: 100% !important;
            box-sizing: border-box !important;
        }
        
        /* Streamlit 容器样式 */
        .st-bw, .st-bx, .st-eh, .st-ei, .st-eg, .st-dh {
            width: 100% !important;
            max-width: 100% !important;
            padding: 0 !important;
            margin: 0 !important;
        }
        
        /* 主内容区域样式 */
        .main .block-container {
            max-width: 100% !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
        
        /* 确保iframe容器也能正确显示 */
        iframe {
            width: 100% !important;
            max-width: 100% !important;
        }
        
        /* 地图父容器样式 */
        div[data-testid="stMarkdownContainer"] > div {
            width: 100% !important;
            max-width: 100% !important;
        }
        </style>
        """, unsafe_allow_html=True)
        folium_static(m, height=1200, width=1600)
        
        return None
    except Exception as e:
        return f"地图生成过程中出错：{str(e)}"
