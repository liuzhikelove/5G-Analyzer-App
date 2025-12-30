# ===== File: map_generator.py (版本 2.0 - 内置坐标转换) =====

import pandas as pd
from pyecharts import options as opts
from pyecharts.charts import BMap, Scatter, HeatMap
from pyecharts.globals import BMapType # 导入 BMapType
import streamlit as st
import math # 导入 math 库用于三角函数和常量

# --- 内置的WGS-84到BD-09坐标转换函数 ---
# 这些常量和函数是实现WGS-84到百度BD-09坐标转换所必需的
x_pi = 3.14159265358979324 * 3000.0 / 180.0
pi = 3.14159265358979324
a = 6378245.0
ee = 0.00669342162296594323

def out_of_china(lat, lon):
    """
    判断是否在国内，不在则不进行转换 (粗略判断)
    :param lat: 纬度
    :param lon: 经度
    :return: True 如果在国外, False 如果在国内
    """
    if lon < 72.004 or lon > 135.0514:
        return True
    if lat < 0.8293 or lat > 55.8271:
        return True
    return False

def _transform(lat, lon):
    """
    WGS-84到GCJ-02 (火星坐标系) 转换的辅助函数
    """
    dlat = _transformlat(lon - 105.0, lat - 35.0)
    dlon = _transformlon(lon - 105.0, lat - 35.0)
    radlat = lat / 180.0 * pi
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * pi)
    dlon = (dlon * 180.0) / (a / sqrtmagic * math.cos(radlat) * pi)
    mglat = lat + dlat
    mglon = lon + dlon
    return [mglat, mglon]

def _transformlat(lon, lat):
    ret = -100.0 + 2.0 * lon + 3.0 * lat + 0.2 * lat * lat + 0.1 * lon * lat + 0.2 * math.sqrt(math.fabs(lon))
    ret += (20.0 * math.sin(6.0 * lon * pi) + 20.0 * math.sin(2.0 * lon * pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lat * pi) + 40.0 * math.sin(lat / 3.0 * pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(lat / 12.0 * pi) + 320 * math.sin(lat * pi / 30.0)) * 2.0 / 3.0
    return ret

def _transformlon(lon, lat):
    ret = 300.0 + lon + 2.0 * lat + 0.1 * lon * lon + 0.1 * lon * lat + 0.1 * math.sqrt(math.fabs(lon))
    ret += (20.0 * math.sin(6.0 * lon * pi) + 20.0 * math.sin(2.0 * lon * pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lon * pi) + 40.0 * math.sin(lon / 3.0 * pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(lon / 12.0 * pi) + 300.0 * math.sin(lon / 30.0 * pi)) * 2.0 / 3.0
    return ret

def wgs84_to_bd09_custom(lon, lat):
    """
    WGS84 (GPS标准) 坐标直接转换为 BD-09 (百度地图) 坐标
    """
    if out_of_china(lat, lon):
        return [lon, lat] # 如果在国外则不进行转换

    # WGS84 -> GCJ02 (火星坐标)
    d = _transform(lat, lon)
    gcj_lon = lon + d[1]
    gcj_lat = lat + d[0]

    # GCJ02 -> BD09 (百度坐标)
    z = math.sqrt(gcj_lon * gcj_lon + gcj_lat * gcj_lat) + 0.00002 * math.sin(gcj_lat * x_pi)
    theta = math.atan2(gcj_lat, gcj_lon) + 0.000003 * math.cos(gcj_lon * x_pi)
    bd_lon = z * math.cos(theta) + 0.0065
    bd_lat = z * math.sin(theta) + 0.006
    return [bd_lon, bd_lat]
# --- 内置坐标转换函数结束 ---


@st.cache_data # 使用Streamlit的缓存功能，避免重复进行耗时的坐标转换
def convert_coords_for_baidu(_df):
    """将DataFrame中的WGS-84坐标批量转换为百度BD-09坐标"""
    df = _df.copy() # 创建副本以避免修改原始数据
    if df is None or df.empty or '经度' not in df.columns or '纬度' not in df.columns:
        return pd.DataFrame() # 如果数据无效，返回一个空的DataFrame
    
    df['经度'] = pd.to_numeric(df['经度'], errors='coerce')
    df['纬度'] = pd.to_numeric(df['纬度'], errors='coerce')
    df.dropna(subset=['经度', '纬度'], inplace=True)
    
    if df.empty:
        return pd.DataFrame()
    
    # --- [核心修改] 调用内置的自定义转换函数 ---
    converted_coords = [wgs84_to_bd09_custom(lon, lat) for lon, lat in zip(df['经度'], df['纬度'])]
    
    df['b_lon'] = [coord[0] for coord in converted_coords]
    df['b_lat'] = [coord[1] for coord in converted_coords]
    return df

def create_baidu_map(df_4g, df_5g, results_df, baidu_ak):
    """使用Pyecharts和百度地图创建可视化图表"""
    
    df_4g_conv = convert_coords_for_baidu(df_4g)
    df_5g_conv = convert_coords_for_baidu(df_5g)
    
    if df_4g_conv.empty:
        return "没有有效的4G数据用于地图显示。请检查'经度'和'纬度'列是否包含有效的数字。"

    df_4g_vis = pd.merge(df_4g_conv, results_df[['小区名称', '分析结果']], on='小区名称', how='left')
    
    categories = {'共站址5G分流小区': [],'共站址5G射频调优小区': [],'非共站址5G分流小区': [],'5G规划建设': [],'其他': []}
    
    for _, row in df_4g_vis.iterrows():
        result_str = str(row.get('分析结果', ''))
        matched = False
        for key in categories.keys():
            if key in result_str:
                categories[key].append(opts.Chart3DPoint(row['b_lon'], row['b_lat'], row['小区名称']))
                matched = True
                break
        if not matched:
            categories['其他'].append([row['b_lon'], row['b_lat'], row['小区名称']])

    heatmap_data_5g = [[r['b_lon'], r['b_lat'], 1] for _, r in df_5g_conv.iterrows()] if not df_5g_conv.empty else []

    center_lon = df_4g_conv['b_lon'].mean() if not df_4g_conv.empty else 116.404 # 默认北京
    center_lat = df_4g_conv['b_lat'].mean() if not df_4g_conv.empty else 39.909 # 默认北京

    bmap = (
        BMap(init_opts=opts.InitOpts(width="100%", height="600px"))
        .add_schema(
            baidu_ak=baidu_ak, 
            center=[center_lon, center_lat], 
            zoom=12, # 初始缩放级别可以调整
            is_roam=True 
        )
        .add_control_panel(
            map_type_control_opts=opts.MapTypeControlOpts(type_=BMapType.MAPTYPE_CONTROL_HYBRID)
        )
    )

    color_map = {
        '共站址5G分流小区': '#28a745',       
        '共站址5G射频调优小区': '#ffc107', 
        '非共站址5G分流小区': '#17a2b8',       
        '5G规划建设': '#dc3545',             
        '其他': '#6c757d'                    
    }
    for name, data in categories.items():
        if data:
            bmap.add(
                series_name=name,
                type_="scatter",
                data_pair=data,
                symbol="pin", 
                symbol_size=15,
                color=color_map.get(name),
                label_opts=opts.LabelOpts(is_show=False), 
            )
    
    if heatmap_data_5g:
        bmap.add(
            series_name="5G站点热力图",
            type_="heatmap",
            data_pair=heatmap_data_5g,
            point_size=5,
            blur_size=15,
        )

    bmap.set_global_opts(
        title_opts=opts.TitleOpts(title="小区分析结果百度地图可视化", pos_left="center"),
        legend_opts=opts.LegendOpts(orient="vertical", pos_top="10%", pos_left="2%"), 
        tooltip_opts=opts.TooltipOpts(
            trigger="item", 
            formatter=lambda params: f"{params.seriesName}<br/>{params.value[2]}" 
        ),
    )

    return bmap.render_embed()
