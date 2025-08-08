# ===== File: app.py =====

import streamlit as st
import pandas as pd
from io import BytesIO
import time

from main_analyzer import analyze_5g_offload

st.set_page_config(page_title="5G分流分析系统", page_icon="📡", layout="wide")
st.title("🛰️ 基于45G距离及方位角的5G分流分析系统")
st.markdown("---")

st.sidebar.header("操作面板")

uploaded_4g_file = st.sidebar.file_uploader("1. 上传4G小区工参表 (Excel)", type=['xlsx', 'xls'])
uploaded_5g_file = st.sidebar.file_uploader("2. 上传5G小区工参表 (Excel)", type=['xlsx', 'xls'])

st.sidebar.markdown("---")

st.sidebar.subheader("共站址算法参数")
d_colo = st.sidebar.number_input("距离阈值 (米)", 1, 500, 50, help="《计划书》P5定义：判断是否为共站址的距离d，典型值50m、100m。")
theta_colo = st.sidebar.number_input("方位角偏差阈值 (度)", 1, 180, 30, help="《计划书》P5定义：判断天线方向是否一致的夹角θ1，典型值30度、60度。")

st.sidebar.subheader("非共站址算法参数")
d_non_colo = st.sidebar.number_input("搜索半径 (米)", 50, 2000, 300, help="《计划书》P5定义：判断非共站址的搜索半径d，典型值300m、400m。")
n_non_colo = st.sidebar.number_input("5G小区数量阈值 (个)", 1, 10, 1, help="《计划书》P5定义：在搜索半径d内需要满足的5G小区数量n，典型值3、4个。")

if 'df_4g' not in st.session_state: st.session_state['df_4g'] = None
if 'df_5g' not in st.session_state: st.session_state['df_5g'] = None
if 'results_df' not in st.session_state: st.session_state['results_df'] = None

if uploaded_4g_file: st.session_state['df_4g'] = pd.read_excel(uploaded_4g_file)
if uploaded_5g_file: st.session_state['df_5g'] = pd.read_excel(uploaded_5g_file)

if st.session_state['df_4g'] is not None:
    st.subheader("4G数据预览")
    st.dataframe(st.session_state['df_4g'].head())

if st.session_state['df_5g'] is not None:
    st.subheader("5G数据预览")
    st.dataframe(st.session_state['df_5g'].head())

st.sidebar.markdown("---")
if st.sidebar.button("🚀 开始分析", type="primary"):
    if st.session_state['df_4g'] is not None and st.session_state['df_5g'] is not None:
        progress_bar = st.progress(0, text="分析准备中...")
        def update_progress(current, total):
            progress_bar.progress(current / total, text=f"正在分析: {current}/{total} 条记录...")

        with st.spinner('系统正在执行核心算法，请稍候...'):
            start_time = time.time()
            st.session_state['results_df'] = analyze_5g_offload(
                st.session_state['df_4g'], st.session_state['df_5g'], 
                d_colo, theta_colo, d_non_colo, n_non_colo, update_progress
            )
            end_time = time.time()
            progress_bar.progress(1.0, text=f"分析完成！耗时 {end_time - start_time:.2f} 秒。")
    else:
        st.sidebar.error("错误：请先上传4G和5G的工参表！")

if st.session_state['results_df'] is not None:
    st.markdown("---")
    st.subheader("📊 分析结果")
    st.dataframe(st.session_state['results_df'])

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        st.session_state['results_df'].to_excel(writer, index=False, sheet_name='5G分流分析结果')
    
    st.download_button("📥 下载分析结果 (Excel文件)", output.getvalue(), "5G分流分析结果.xlsx", "application/vnd.ms-excel")