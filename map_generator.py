# ===== File: map_generator.py (最终修正版 v2) =====

import pandas as pd
from pyecharts import options as opts
from pyecharts.charts import BMap, Scatter, HeatMap
from pyecharts.globals import BMapType
import coord_convert as cc
import streamlit as st

@st.cache_data
def convert_coords_for_baidu(_df):
    """将DataFrame中的WGS-84坐标批量转换为百度BD-09坐标"""
    df = _df.copy()
    if df is None or df.empty or '经度' not in df.columns or '纬度' not in df.columns:
        return pd.DataFrame()
    
    df['经度'] = pd.to_numeric(df['经度'], errors='coerce')
    df['纬度'] = pd.to_numeric(df['纬度'], errors='coerce')
    df.dropna(subset=['经度', '纬度'], inplace=True)
    
    if df.empty:
        return pd.DataFrame()
    
    # --- [核心修复] 使用正确的函数名：wgs_to_gcj 和 gcj_to_bd ---
    converted_coords = []
    for lon, lat in zip(df['经度'], df['纬度']):
        gcj02_lon, gcj02_lat = cc.wgs_to_gcj(lon, lat)
        bd09_lon, bd09_lat = cc.gcj_to_bd(gcj02_lon, gcj02_lat)
        converted_coords.append((bd09_lon, bd09_lat))

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
                categories[key].append([row['b_lon'], row['b_lat'], row['小区名称']])
                matched = True
                break
        if not matched:
            categories['其他'].append([row['b_lon'], row['b_lat'], row['小区名称']])

    heatmap_data_5g = [[r['b_lon'], r['b_lat'], 1] for _, r in df_5g_conv.iterrows()] if not df_5g_conv.empty else []

    center_lon = df_4g_conv['b_lon'].mean()
    center_lat = df_4g_conv['b_lat'].mean()

    bmap = (
        BMap(init_opts=opts.InitOpts(width="100%", height="600px"))
        .add_schema(baidu_ak=baidu_ak, center=[center_lon, center_lat], zoom=14, is_roam=True)
        .add_control_panel(map_type_control_opts=opts.MapTypeControlOpts(type_=BMapType.MAPTYPE_CONTROL_HYBRID))
    )

    color_map = {'共站址5G分流小区': '#28a745','共站址5G射频调优小区': '#ffc107','非共站址5G分流小区': '#17a2b8','5G规划建设': '#dc3545','其他': '#6c757d'}
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
            formatter=lambda params: f"{params.seriesName}<br/>{params.data.value[2]}" if params.data else ""
        ),
    )

    return bmap.render_embed()
