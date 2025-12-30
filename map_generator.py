# ===== File: map_generator.py =====

import pandas as pd
from pyecharts import options as opts
from pyecharts.charts import BMap, Scatter, HeatMap
from pyecharts.globals import BMapType # 导入 BMapType
import coord_convert as cc
import streamlit as st

# 使用Streamlit的缓存功能，避免重复进行耗时的坐标转换
@st.cache_data
def convert_coords_for_baidu(_df):
    """将DataFrame中的WGS-84坐标批量转换为百度BD-09坐标"""
    df = _df.copy() # 创建副本以避免修改原始数据
    if df is None or df.empty or '经度' not in df.columns or '纬度' not in df.columns:
        return pd.DataFrame() # 如果数据无效，返回一个空的DataFrame
    
    # 强制将经纬度列转换为数字类型，无效值将变为NaN
    df['经度'] = pd.to_numeric(df['经度'], errors='coerce')
    df['纬度'] = pd.to_numeric(df['纬度'], errors='coerce')
    # 删除任何包含无效经纬度的行
    df.dropna(subset=['经度', '纬度'], inplace=True)
    
    if df.empty:
        return pd.DataFrame()
    
    # 使用列表推导式进行高效的批量转换
    converted_coords = [cc.wgs84_to_bd09(lon, lat) for lon, lat in zip(df['经度'], df['纬度'])]
    
    # 将转换后的坐标添加到新的列中
    df['b_lon'] = [coord[0] for coord in converted_coords]
    df['b_lat'] = [coord[1] for coord in converted_coords]
    return df

def create_baidu_map(df_4g, df_5g, results_df, baidu_ak):
    """使用Pyecharts和百度地图创建可视化图表"""
    
    # --- 1. 坐标转换 ---
    df_4g_conv = convert_coords_for_baidu(df_4g)
    df_5g_conv = convert_coords_for_baidu(df_5g)
    
    if df_4g_conv.empty:
        return "没有有效的4G数据用于地图显示。请检查'经度'和'纬度'列是否包含有效的数字。"

    # --- 2. 数据准备 ---
    # 将分析结果合并到4G数据中，以便后续的可视化
    df_4g_vis = pd.merge(df_4g_conv, results_df[['小区名称', '分析结果']], on='小区名称', how='left')
    
    # 按分析结果对4G数据进行分组，为不同类别的点分配不同的颜色
    categories = {
        '共站址5G分流小区': [],
        '共站址5G射频调优小区': [],
        '非共站址5G分流小区': [],
        '5G规划建设': [],
        '其他': []
    }
    
    for _, row in df_4g_vis.iterrows():
        result_str = str(row.get('分析结果', ''))
        matched = False
        for key in categories.keys():
            if key in result_str:
                # 准备散点图的数据格式：[经度, 纬度, 小区名称]
                categories[key].append([row['b_lon'], row['b_lat'], row['小区名称']])
                matched = True
                break
        if not matched:
            categories['其他'].append([row['b_lon'], row['b_lat'], row['小区名称']])

    # 准备5G热力图的数据格式：[经度, 纬度, 权重]
    heatmap_data_5g = [[r['b_lon'], r['b_lat'], 1] for _, r in df_5g_conv.iterrows()] if not df_5g_conv.empty else []

    # --- 3. 创建地图实例 ---
    # 计算地图的中心点
    center_lon = df_4g_conv['b_lon'].mean()
    center_lat = df_4g_conv['b_lat'].mean()

    bmap = (
        BMap(init_opts=opts.InitOpts(width="100%", height="600px"))
        .add_schema(
            baidu_ak=baidu_ak, 
            center=[center_lon, center_lat], 
            zoom=14, 
            is_roam=True # 允许用户缩放和平移地图
        )
        # 添加地图类型控件（例如：街道、卫星、混合）
        .add_control_panel(
            map_type_control_opts=opts.MapTypeControlOpts(type_=BMapType.MAPTYPE_CONTROL_HYBRID)
        )
    )

    # --- 4. 添加图层 ---
    # 定义每个类别的颜色
    color_map = {
        '共站址5G分流小区': '#28a745',       # 成功绿
        '共站址5G射频调优小区': '#ffc107', # 警告黄
        '非共站址5G分流小区': '#17a2b8',       # 信息蓝
        '5G规划建设': '#dc3545',             # 危险红
        '其他': '#6c757d'                    # 中性灰
    }
    # 循环添加不同类别的4G小区散点图
    for name, data in categories.items():
        if data:
            bmap.add(
                series_name=name,
                type_="scatter",
                data_pair=data,
                symbol="pin", # 使用大头针形状的标记
                symbol_size=15,
                color=color_map.get(name),
                label_opts=opts.LabelOpts(is_show=False), # 不直接显示标签，悬停时显示
            )
    
    # 添加5G热力图图层
    if heatmap_data_5g:
        bmap.add(
            series_name="5G站点热力图",
            type_="heatmap",
            data_pair=heatmap_data_5g,
            point_size=5,
            blur_size=15,
        )

    # --- 5. 配置全局选项 ---
    bmap.set_global_opts(
        title_opts=opts.TitleOpts(title="小区分析结果百度地图可视化", pos_left="center"),
        legend_opts=opts.LegendOpts(orient="vertical", pos_top="10%", pos_left="2%"), # 图例
        tooltip_opts=opts.TooltipOpts(
            trigger="item", 
            formatter=lambda params: f"{params.seriesName}<br/>{params.value[2]}" # 自定义悬停提示框内容
        ),
    )

    # 将图表渲染成可以在网页中嵌入的HTML代码
    return bmap.render_embed()