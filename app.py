# ===== File: app.py (版本 4.1 - 调整分页控件位置) =====

import streamlit as st
import pandas as pd
from io import BytesIO
import time
import pydeck as pdk

from main_analyzer import analyze_5g_offload
from algorithms import create_sector_polygon

REQUIRED_COLUMNS = ['小区名称', '经度', '纬度', '方位角']

# --- [核心修改] 调整分页函数的布局 ---
def display_paginated_dataframe(df, title):
    st.subheader(title)
    if df is None or df.empty:
        st.warning("请先上传文件。")
        return
        
    page_size = 10
    total_pages = -(-len(df) // page_size)

    # --- 1. 先渲染表格 ---
    # 为了让页码选择器能拿到正确的页码值，我们需要先处理它
    # 但是我们可以把它的显示放到后面
    page_num_key = f"page_{title}"
    if page_num_key not in st.session_state:
        st.session_state[page_num_key] = 1
    
    # 提前获取页码，但不显示控件
    page_num = st.session_state[page_num_key]

    # 根据页码切片数据
    start_idx = (page_num - 1) * page_size
    end_idx = start_idx + page_size
    st.dataframe(df.iloc[start_idx:end_idx])

    # --- 2. 再渲染分页控件，并使其右对齐 ---
    # 创建列布局，让一个空的列把分页控件推到右边
    col1, col2 = st.columns([3, 1]) # 第一个列占3/4宽度，第二个占1/4
    
    with col1:
        # 这个列是空的，只是用来占位
        st.write("") 
        
    with col2:
        # 创建一个容器来组合控件
        pagination_container = st.container()
        # 将总计信息和页码选择器放在同一行
        sub_col1, sub_col2 = pagination_container.columns([2,1])
        with sub_col1:
             st.markdown(f"<div style='text-align: right; padding-top: 10px;'>总计: {len(df)} 条，共 {total_pages} 页</div>", unsafe_allow_html=True)
        with sub_col2:
            # 使用 st.session_state 来管理页码选择器的状态
            st.number_input("页码", min_value=1, max_value=total_pages, step=1, key=page_num_key, label_visibility="collapsed")


# --- 地图创建函数 (无改动) ---
def create_map(df_4g, df_5g, results_df):
    df_4g_vis = df_4g.copy()
    df_4g_vis = pd.merge(df_4g_vis, results_df[['小区名称', '分析结果']], on='小区名称', how='left')
    color_map = {'共站址5G分流小区': [0, 255, 0, 150],'共站址5G射频调优小区': [255, 165, 0, 150],'非共站址5G分流小区': [0, 191, 255, 150],'5G规划建设': [255, 0, 0, 150]}
    df_4g_vis['color'] = df_4g_vis['分析结果'].apply(lambda x: next((color for key, color in color_map.items() if key in str(x)), [128, 128, 128, 100]))
    df_4g_vis['polygon'] = df_4g_vis.apply(lambda row: create_sector_polygon(row['经度'], row['纬度'], row['方位角'], radius_m=250, angle_deg=60), axis=1)
    sector_layer_4g = pdk.Layer('PolygonLayer', data=df_4g_vis, get_polygon='polygon', get_fill_color='color', get_line_color=[255, 255, 255], get_line_width=5, pickable=True, auto_highlight=True)
    heatmap_layer_5g = pdk.Layer('HeatmapLayer', data=df_5g, get_position=['经度', '纬度'], opacity=0.8, threshold=0.1, get_weight=1)
    initial_view_state = pdk.ViewState(latitude=df_4g_vis['纬度'].mean(), longitude=df_4g_vis['经度'].mean(), zoom=13, pitch=50)
    tooltip = {"html": "<b>小区名称:</b> {小区名称} <br/> <b>分析结果:</b> {分析结果}", "style": {"backgroundColor": "steelblue", "color": "white"}}
    st.pydeck_chart(pdk.Deck(map_style='mapbox://styles/mapbox/dark-v9', initial_view_state=initial_view_state, layers=[heatmap_layer_5g, sector_layer_4g], tooltip=tooltip))


# --- 主应用界面与逻辑 (基本无改动) ---
st.set_page_config(page_title="基于45G距离及方位角的5G分流分析系统", page_icon="📡", layout="wide")
st.title("🛰️ 基于45G距离及方位角的5G分流分析系统")

st.sidebar.header("操作面板")
uploaded_4g_file = st.sidebar.file_uploader("1. 上传4G小区工参表 (Excel)", type=['xlsx', 'xls'])
uploaded_5g_file = st.sidebar.file_uploader("2. 上传5G小区工参表 (Excel)", type=['xlsx', 'xls'])

st.sidebar.markdown("---")
st.sidebar.subheader("算法参数")
d_colo = st.sidebar.number_input("共站址距离阈值 (米)", 1, 500, 50)
theta_colo = st.sidebar.number_input("共站址方位角偏差阈值 (度)", 1, 180, 30)
d_non_colo = st.sidebar.number_input("非共站址搜索半径 (米)", 50, 2000, 300)
n_non_colo = st.sidebar.number_input("非共站址5G小区数量阈值 (个)", 1, 10, 1)
st.sidebar.markdown("---")

if 'df_4g' not in st.session_state: st.session_state.df_4g = None
if 'df_5g' not in st.session_state: st.session_state.df_5g = None

if uploaded_4g_file: st.session_state.df_4g = pd.read_excel(uploaded_4g_file)
if uploaded_5g_file: st.session_state.df_5g = pd.read_excel(uploaded_5g_file)

display_paginated_dataframe(st.session_state.df_4g, "4G数据预览")
display_paginated_dataframe(st.session_state.df_5g, "5G数据预览")

if st.sidebar.button("🚀 开始分析", type="primary"):
    if st.session_state.df_4g is not None and st.session_state.df_5g is not None:
        df_4g = st.session_state.df_4g
        df_5g = st.session_state.df_5g

        missing_4g_cols = [col for col in REQUIRED_COLUMNS if col not in df_4g.columns]
        missing_5g_cols = [col for col in REQUIRED_COLUMNS if col not in df_5g.columns]

        if missing_4g_cols or missing_5g_cols:
            error_message = "文件表头不符合标准！\n"
            if missing_4g_cols: error_message += f"\n4G文件缺少以下列: **{', '.join(missing_4g_cols)}**"
            if missing_5g_cols: error_message += f"\n5G文件缺少以下列: **{', '.join(missing_5g_cols)}**"
            error_message += f"\n\n请确保两个文件都包含: **{', '.join(REQUIRED_COLUMNS)}**"
            st.error(error_message)
        else:
            for col in ['经度', '纬度', '方位角']:
                df_4g[col] = pd.to_numeric(df_4g[col], errors='coerce')
                df_5g[col] = pd.to_numeric(df_5g[col], errors='coerce')
            df_4g.dropna(subset=REQUIRED_COLUMNS, inplace=True)
            df_5g.dropna(subset=REQUIRED_COLUMNS, inplace=True)

            progress_bar = st.progress(0, text="分析准备中...")
            def update_progress(current, total):
                progress_bar.progress(current / total, text=f"正在分析: {current}/{total} 条记录...")

            with st.spinner('系统正在执行核心算法...'):
                results_df = analyze_5g_offload(df_4g, df_5g, d_colo, theta_colo, d_non_colo, n_non_colo, update_progress)

            st.markdown("---")
            st.subheader("🗺️ 地图可视化结果")
            st.info("绿色: 分流小区 | 橙色: 射频调优 | 蓝色: 非共站址分流 | 红色: 规划建设 | 热力图: 5G站点分布密度")
            create_map(df_4g, df_5g, results_df)

            st.markdown("---")
            st.subheader("📊 详细分析结果")
            st.dataframe(results_df)
            
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                results_df.to_excel(writer, index=False, sheet_name='5G分流分析结果')
            st.download_button("📥 下载分析结果 (Excel文件)", output.getvalue(), "5G分流分析结果.xlsx", "application/vnd.ms-excel")
    else:
        st.sidebar.error("错误：请先上传4G和5G的工参表！")
