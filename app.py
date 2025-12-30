# ===== File: app.py (版本 5.4 - 健壮的表头解析) =====

import streamlit as st
import pandas as pd
from io import BytesIO
import time
import streamlit.components.v1 as components
import gc

from main_analyzer import analyze_5g_offload
from map_generator import create_baidu_map

REQUIRED_COLUMNS = ['小区名称', '经度', '纬度', '方位角']

# --- [核心修改] 创建一个健壮的数据加载和验证函数 ---
def load_and_validate_data(uploaded_file):
    """
    高效加载数据，并能自动处理表头中的前后空格。
    """
    # 1. 只读取表头行，以获取所有列名，非常节省内存
    all_cols = pd.read_excel(uploaded_file, nrows=0).columns
    
    # 2. 清理每个列名，去除前后的空格，并创建一个映射
    #    例如: {'小区名称': ' 小区名称 '}
    cleaned_cols_map = {col.strip(): col for col in all_cols}
    
    # 3. 在清理过的列名中检查是否缺少必需的列
    missing_cols = [req_col for req_col in REQUIRED_COLUMNS if req_col not in cleaned_cols_map]
    if missing_cols:
        # 如果缺少，直接抛出带有清晰信息的错误
        raise ValueError(f"文件缺少以下必需的列: {', '.join(missing_cols)}")
        
    # 4. 找出我们需要加载的列的原始名称（可能带有空格）
    cols_to_load = [cleaned_cols_map[req_col] for req_col in REQUIRED_COLUMNS]
    
    # 5. 使用 'usecols' 高效加载数据，只加载我们需要的列
    df = pd.read_excel(uploaded_file, usecols=cols_to_load)
    
    # 6. 将加载进来的、可能带有空格的列名，重命名为标准的、干净的名称
    rename_map = {cleaned_cols_map[req_col]: req_col for req_col in REQUIRED_COLUMNS}
    df.rename(columns=rename_map, inplace=True)
    
    return df

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

# --- 主程序代码 ---
st.set_page_config(page_title="5G分流分析系统 (百度地图版)", page_icon="📡", layout="wide")
st.title("🛰️ 5G分流分析系统 (百度地图版)")
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

if 'df_4g_preview' not in st.session_state: st.session_state.df_4g_preview = None
if 'df_5g_preview' not in st.session_state: st.session_state.df_5g_preview = None

preview_4g_placeholder = st.empty(); preview_5g_placeholder = st.empty()
if uploaded_4g_file and st.session_state.df_4g_preview is None: st.session_state.df_4g_preview = pd.read_excel(uploaded_4g_file)
if uploaded_5g_file and st.session_state.df_5g_preview is None: st.session_state.df_5g_preview = pd.read_excel(uploaded_5g_file)
with preview_4g_placeholder.container(): display_paginated_dataframe(st.session_state.df_4g_preview, "4G数据预览")
with preview_5g_placeholder.container(): display_paginated_dataframe(st.session_state.df_5g_preview, "5G数据预览")

if st.sidebar.button("🚀 开始分析", type="primary"):
    if uploaded_4g_file is not None and uploaded_5g_file is not None:
        if "BAIDU_AK" not in st.secrets or not st.secrets["BAIDU_AK"]:
            st.error("错误：请先在Streamlit Cloud的Secrets中配置您的百度地图AK！")
        else:
            try:
                preview_4g_placeholder.empty(); preview_5g_placeholder.empty()
                with st.spinner("正在高效加载和验证数据..."):
                    df_4g = load_and_validate_data(uploaded_4g_file)
                    df_5g = load_and_validate_data(uploaded_5g_file)
                
                progress_bar = st.progress(0, text="分析准备中...")
                def update_progress(current, total):
                    progress_bar.progress(current/total if total>0 else 0, text=f"正在分析: {current}/{total} 条记录...")
                
                results_df = analyze_5g_offload(df_4g, df_5g, d_colo, theta_colo, d_non_colo, n_non_colo, update_progress)
                progress_bar.progress(1.0, text="分析完成！正在准备结果展示...")
                
                del df_4g; del df_5g; gc.collect()
                
                st.markdown("---"); st.subheader("🗺️ 百度地图可视化结果")
                with st.spinner('正在生成百度地图...'):
                    baidu_ak = st.secrets["BAIDU_AK"]
                    map_html = create_baidu_map(st.session_state.df_4g_preview, st.session_state.df_5g_preview, results_df, baidu_ak)
                if "没有有效" in str(map_html): st.warning(map_html)
                else: components.html(map_html, height=610, scrolling=True)
                
                st.markdown("---"); st.subheader("📊 详细分析结果")
                st.dataframe(results_df)
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer: results_df.to_excel(writer, index=False, sheet_name='5G分流分析结果')
                st.download_button("📥 下载分析结果", output.getvalue(), "5G分流分析结果.xlsx", "application/vnd.ms-excel")
            except ValueError as e:
                st.error(f"文件表头不符合标准！\n\n**错误详情**: {e}\n\n**请确保** 两个文件都包含以下列（且没有拼写错误）: **`{REQUIRED_COLUMNS}`**")
            except Exception as e:
                st.error(f"分析过程中出现意外错误: {e}")
    else:
        st.sidebar.error("错误：请先上传4G和5G的工参表！")
