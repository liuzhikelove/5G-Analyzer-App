# ===== File: map_generator.py (最终稳定版 - 移除控件) =====

import pandas as pd
from pyecharts import options as opts
from pyecharts.charts import BMap, Scatter, HeatMap
from pyecharts.globals import BMapType
import streamlit as st
import math

# --- 内置坐标转换算法 ---
x_pi = 3.14159265358979324 * 3000.0 / 180.0
pi = 3.1415926535897932384626
a = 6378245.0
ee = 0.00669342162296594323

def _transform_lat(lng, lat):
    ret = -100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat + 0.1 * lng * lat + 0.2 * math.sqrt(math.fabs(lng))
    ret += (20.0 * math.sin(6.0 * lng * pi) + 20.0 * math.sin(2.0 * lng * pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lat * pi) + 40.0 * math.sin(lat / 3.0 * pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(lat / 12.0 * pi) + 320 * math.sin(lat * pi / 30.0)) * 2.0 / 3.0
    return ret

def _transform_lng(lng, lat):
    ret = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng + 0.1 * lng * lat + 0.1 * math.sqrt(math.fabs(lng))
    ret += (20.0 * math.sin(6.0 * lng * pi) + 20.0 * math.sin(2.0 * lng * pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lng * pi) + 40.0 * math.sin(lng / 3.0 * pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(lng / 12.0 * pi) + 300.0 * math.sin(lng / 30.0 * pi)) * 2.0 / 3.0
    return ret

def wgs84_to_gcj02(lng, lat):
    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlng = _transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * pi
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * pi)
    dlng = (dlng * 180.0) / (a / sqrtmagic * math.cos(radlat) * pi)
    return [lng + dlng, lat + dlat]

def gcj02_to_bd09(lng, lat):
    z = math.sqrt(lng * lng + lat * lat) + 0.00002 * math.sin(lat * x_pi)
    theta = math.atan2(lat, lng) + 0.000003 * math.cos(lng * x_pi)
    return [z * math.cos(theta) + 0.0065, z * math.sin(theta) + 0.006]

@st.cache_data
def convert_coords_for_baidu(_df):
    df = _df.copy()
    if df is None or df.empty or '经度' not in df.columns or '纬度' not in df.columns: return pd.DataFrame()
    df['经度'] = pd.to_numeric(df['经度'], errors='coerce'); df['纬度'] = pd.to_numeric(df['纬度'], errors='coerce')
    df.dropna(subset=['经度', '纬度'], inplace=True)
    if df.empty: return pd.DataFrame()
    converted_coords = []
    for lon, lat in zip(df['经度'], df['纬度']):
        gcj_lon, gcj_lat = wgs84_to_gcj02(lon, lat)
        bd_lon, bd_lat = gcj02_to_bd09(gcj_lon, gcj_lat)
        converted_coords.append((bd_lon, bd_lat))
    df['b_lon'] = [coord[0] for coord in converted_coords]; df['b_lat'] = [coord[1] for coord in converted_coords]
    return df

def create_baidu_map(df_4g, df_5g, results_df, baidu_ak):
    df_4g_conv = convert_coords_for_baidu(df_4g); df_5g_conv = convert_coords_for_baidu(df_5g)
    if df_4g_conv.empty: return "没有有效的4G数据用于地图显示。"
    df_4g_vis = pd.merge(df_4g_conv, results_df[['小区名称', '分析结果']], on='小区名称', how='left')
    categories = {'共站址5G分流小区': [],'共站址5G射频调优小区': [],'非共站址5G分流小区': [],'5G规划建设': [],'其他': []}
    for _, row in df_4g_vis.iterrows():
        result_str = str(row.get('分析结果', '')); matched = False
        for key in categories.keys():
            if key in result_str: categories[key].append([row['b_lon'], row['b_lat'], row['小区名称']]); matched = True; break
        if not matched: categories['其他'].append([row['b_lon'], row['b_lat'], row['小区名称']])
    heatmap_data_5g = [[r['b_lon'], r['b_lat'], 1] for _, r in df_5g_conv.iterrows()] if not df_5g_conv.empty else []
    center_lon = df_4g_conv['b_lon'].mean(); center_lat = df_4g_conv['b_lat'].mean()
    
    bmap = (
        BMap(init_opts=opts.InitOpts(width="100%", height="600px"))
        .add_schema(baidu_ak=baidu_ak, center=[center_lon, center_lat], zoom=14, is_roam=True)
        # --- [核心修改] 下面这行导致错误的代码已经被删除 ---
        # .add_control_panel(map_type_control_opts=opts.MapTypeControlOpts(type_=BMapType.MAPTYPE_CONTROL_HYBRID))
    )

    color_map = {'共站址5G分流小区': '#28a745','共站址5G射频调优小区': '#ffc107','非共站址5G分流小区': '#17a2b8','5G规划建设': '#dc3545','其他': '#6c757d'}
    for name, data in categories.items():
        if data: bmap.add(series_name=name, type_="scatter", data_pair=data, symbol="pin", symbol_size=15, color=color_map.get(name), label_opts=opts.LabelOpts(is_show=False))
    if heatmap_data_5g: bmap.add(series_name="5G站点热力图", type_="heatmap", data_pair=heatmap_data_5g, point_size=5, blur_size=15)
    bmap.set_global_opts(title_opts=opts.TitleOpts(title="小区分析结果百度地图可视化", pos_left="center"), legend_opts=opts.LegendOpts(orient="vertical", pos_top="10%", pos_left="2%"), tooltip_opts=opts.TooltipOpts(trigger="item", formatter=lambda params: f"{params.seriesName}<br/>{params.data.value[2]}" if params.data else ""))
    return bmap.render_embed()
