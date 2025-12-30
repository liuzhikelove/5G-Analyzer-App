# ===== File: app.py (版本 5.1 - 内存优化版) =====

import streamlit as st
import pandas as pd
from io import BytesIO
import time
import streamlit.components.v1 as components
import gc # 导入垃圾回收模块

from main_analyzer import analyze_5g_offload
from map_generator import create_baidu_map

REQUIRED_COLUMNS = ['小区名称', '经度', '纬度', '方位角']

def display_paginated_dataframe(df, title):
    st.subheader(title)
    if df is None or df.empty: st.warning("请先上传文件。"); return
    page_size = 10; total_pages = -(-len(df) // page_size) if len(df) > 0 else 1; page_num_key = f"page_{title}"
    if page_num_key not in st.session_state: st.session_state[page_num_key] = 1
    page_num = st.session_state[page_num_key]; start_idx = (page_num - 1) * page_size; end_idx = start_idx + page_size
    st.dataframe(df.iloc[start_idx:end_idx])
    col1, col2 = st.columns([3, 1]); 
    with col1: st.write("");
    with col2:
        pagination_container = st.container(); sub_col1, sub_col2 = pagination_container.columns([2,1])
        with sub_col1: st.markdown(f"<div style='text-align: right; padding-top: 10px;'>总计: {len(df)} 条，共 {total_pages} 页</div>", unsafe_allow_html=True)
        with sub_col2: st.number_input("页码", 1, total_pages, step=1, key=page_num_key, label_visibility="collapsed")

st.set_page_config(page_title="5G分流分析系统 (百度地图版)", page_icon="📡", layout="wide")
st.title("🛰️ 5G分流分析系统 (百度地图版)")
st.sidebar.header("操作面板")
uploaded_4g_file = st.sidebar.file_uploader("1. 上传4G小区工参表 (Excel)", type=['xlsx', 'xls'])
uploaded_5g_file = st.sidebar.file_uploader("2. 上传5G小区工参表 (Excel)", type=['xlsx',xls'])
st.sidebar.markdown("---")
st.sidebar.subheader("算法参数")
d_colo = st.sidebar.number_input("共站址距离阈值 (米)", 1, 500, 50)
theta_colo = st.sidebar.number_input("共站址方位角偏差阈值 (度)", 1, 180, 30)
d_non_colo = st.sidebar.number_input("非共站址搜索半径 (米)", 50, 2000, 300)
n_non_colo = st.sidebar.number_input("非共站址5G小区数量阈值 (个)", 1, 10, 1)
st.sidebar.markdown("---")

# --- [核心修改] 分开处理预览数据和分析数据 ---
if 'df_4g_preview' not in st.session_state: st.session_state.df_4g_preview = None
if 'df_5g_preview' not in st.session_state: st.session_state.df_5g_preview = None

if uploaded_4g_file and st.session_state.df_4g_preview is None:
    with st.spinner("正在加载4G文件预览..."):
        st.session_state.df_4g_preview = pd.read_excel(uploaded_4g_file)
if uploaded_5g_file and st.session_state.df_5g_preview is None:
    with st.spinner("正在加载5G文件预览..."):
        st.session_state.df_5g_preview = pd.read_excel(uploaded_5g_file)

display_paginated_dataframe(st.session_state.df_4g_preview, "4G数据预览")
display_paginated_dataframe(st.session_state.df_5g_preview, "5G数据预览")

if st.sidebar.button("🚀 开始分析", type="primary"):
    if uploaded_4g_file is not None and uploaded_5g_file is not None:
        if "BAIDU_AK" not in st.secrets or not st.secrets["BAIDU_AK"]:
            st.error("错误：请先在Streamlit Cloud的Secrets中配置您的百度地图AK！")
        else:
            try:
                # --- [核心优化] 只读取必需的列进行分析，大大降低内存占用 ---
                with st.spinner("正在高效加载分析数据..."):
                    df_4g = pd.read_excel(uploaded_4g_file, usecols=REQUIRED_COLUMNS)
                    df_5g = pd.read_excel(uploaded_5g_file, usecols=REQUIRED_COLUMNS)
                
                with st.spinner('系统正在执行核心算法...'):
                    results_df = analyze_5g_offload(df_4g, df_5g, d_colo, theta_colo, d_non_colo, n_non_colo)
                
                # 手动释放不再需要的DataFrame内存
                del df_4g
                del df_5g
                gc.collect()

                st.markdown("---")
                st.subheader("🗺️ 百度地图可视化结果")
                with st.spinner('正在生成百度地图...'):
                    baidu_ak = st.secrets["BAIDU_AK"]
                    # 传递原始的预览DataFrame用于地图上的信息展示
                    map_html = create_baidu_map(st.session_state.df_4g_preview, st.session_state.df_5g_preview, results_df, baidu_ak)
                
                if "没有有效" in str(map_html):
                    st.warning(map_html)
                else:
                    components.html(map_html, height=610, scrolling=True)

                st.markdown("---")
                st.subheader("📊 详细分析结果")
                st.dataframe(results_df)
                
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    results_df.to_excel(writer, index=False, sheet_name='5G分流分析结果')
                st.download_button("📥 下载分析结果", output.getvalue(), "5G分流分析结果.xlsx", "application/vnd.ms-excel")

            except ValueError as e:
                st.error(f"文件表头不符合标准！错误: {e}. 请确保两个文件都包含: {REQUIRED_COLUMNS}")
            except Exception as e:
                st.error(f"分析过程中出现意外错误: {e}")
    else:
        st.sidebar.error("错误：请先上传4G和5G的工参表！")
