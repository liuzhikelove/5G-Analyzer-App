# ===== File: app.py (最终稳定版 v5.5) =====
import streamlit as st
import pandas as pd
from io import BytesIO
import time
import streamlit.components.v1 as components
import gc
from main_analyzer import analyze_5g_offload
from map_generator import create_folium_map
REQUIRED_COLUMNS = ['小区名称', '经度', '纬度', '方位角']
def load_and_validate_data(uploaded_file, file_type):
    if uploaded_file is None: 
        raise ValueError(f"请先上传{file_type}文件。")
    try:
        # 读取所有列名，用于验证
        all_cols = pd.read_excel(uploaded_file, nrows=0).columns
        
        # 清理列名空格并创建映射
        cleaned_cols_map = {col.strip(): col for col in all_cols}
        
        # 验证必需列
        missing_cols = [req_col for req_col in REQUIRED_COLUMNS if req_col not in cleaned_cols_map]
        if missing_cols: 
            raise ValueError(f"{file_type}文件缺少以下必需的列: {', '.join(missing_cols)}")
        
        # 加载所有数据，但只保留必需列
        cols_to_load = [cleaned_cols_map[req_col] for req_col in REQUIRED_COLUMNS]
        df = pd.read_excel(uploaded_file, usecols=cols_to_load)
        
        # 重命名列为标准名称
        rename_map = {cleaned_cols_map[req_col]: req_col for req_col in REQUIRED_COLUMNS}
        df.rename(columns=rename_map, inplace=True)
        
        # 验证数据完整性
        if df.empty:
            raise ValueError(f"{file_type}文件中没有有效的数据行！")
        
        # 将数值列转换为数字类型
        for col in ['经度', '纬度', '方位角']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 过滤掉包含无效数值的行
        initial_count = len(df)
        df.dropna(subset=['经度', '纬度', '方位角'], inplace=True)
        invalid_count = initial_count - len(df)
        
        if invalid_count > 0:
            st.warning(f"{file_type}文件中发现{invalid_count}行包含无效数值数据，已自动过滤。")
        
        # 验证过滤后的数据是否为空
        if df.empty:
            raise ValueError(f"{file_type}文件中没有有效的数据行！")
        
        # 验证地理坐标的合理性（中国地区大致范围）
        invalid_lon = ((df['经度'] < 73) | (df['经度'] > 135)).sum()
        invalid_lat = ((df['纬度'] < 18) | (df['纬度'] > 53)).sum()
        invalid_azimuth = ((df['方位角'] < 0) | (df['方位角'] > 360)).sum()
        
        total_invalid = invalid_lon + invalid_lat + invalid_azimuth
        if total_invalid > 0:
            # 再次过滤掉超出合理范围的数据
            df = df[(df['经度'] >= 73) & (df['经度'] <= 135) & 
                   (df['纬度'] >= 18) & (df['纬度'] <= 53) & 
                   (df['方位角'] >= 0) & (df['方位角'] <= 360)]
            st.warning(f"{file_type}文件中发现{total_invalid}行数据超出合理范围，已自动过滤。")
        
        # 最后检查数据是否为空
        if df.empty:
            raise ValueError(f"{file_type}文件中没有有效的数据行！")
        
        # 验证小区名称列不为空
        if df['小区名称'].isnull().any():
            raise ValueError(f"{file_type}文件中的'小区名称'列包含空值！")
        

        
        return df
    except ValueError as ve:
        # 直接传递已格式化的错误信息
        raise ve
    except pd.errors.EmptyDataError:
        raise ValueError(f"{file_type}文件为空或没有数据行！")
    except pd.errors.ParserError:
        raise ValueError(f"{file_type}文件格式错误！请确保上传的是有效的Excel文件（.xlsx或.xls格式）。")
    except Exception as e:
        raise ValueError(f"读取{file_type}文件时出错: {type(e).__name__}: {str(e)}. 请确保文件是有效的Excel格式。")
def display_paginated_dataframe(df, title):
    st.subheader(title)
    if df is None or df.empty: st.warning("请先上传文件。"); return
    page_size = 10; total_pages = -(-len(df) // page_size) if len(df) > 0 else 1; page_num_key = f"page_{title}"
    if page_num_key not in st.session_state: st.session_state[page_num_key] = 1
    page_num = st.session_state.get(page_num_key, 1); start_idx = (page_num - 1) * page_size; end_idx = start_idx + page_size
    st.dataframe(df.iloc[start_idx:end_idx])
    col1, col2 = st.columns([3, 1]); 
    with col1: st.write("");
    with col2:
        pagination_container = st.container(); sub_col1, sub_col2 = pagination_container.columns([2,1])
        with sub_col1: st.markdown(f"<div style='text-align: right; padding-top: 10px;'>总计: {len(df)} 条，共 {total_pages} 页</div>", unsafe_allow_html=True)
        with sub_col2: st.number_input("页码", 1, total_pages, step=1, key=page_num_key, label_visibility="collapsed")
st.set_page_config(page_title="5G分流分析系统 (Leaflet地图版)", page_icon="📡", layout="wide"); st.title("🛰️ 5G分流分析系统 (Leaflet地图版)")
st.sidebar.header("操作面板"); uploaded_4g_file = st.sidebar.file_uploader("1. 上传4G小区工参表 (Excel)", type=['xlsx', 'xls']); uploaded_5g_file = st.sidebar.file_uploader("2. 上传5G小区工参表 (Excel)", type=['xlsx', 'xls'])
st.sidebar.markdown("---"); st.sidebar.subheader("算法参数"); d_colo = st.sidebar.number_input("共站址距离阈值 (米)", 1, 500, 50); theta_colo = st.sidebar.number_input("共站址方位角偏差阈值 (度)", 1, 180, 30); d_non_colo = st.sidebar.number_input("非共站址搜索半径 (米)", 50, 2000, 300); n_non_colo = st.sidebar.number_input("非共站址5G小区数量阈值 (个)", 1, 10, 1)
st.sidebar.markdown("---")

# 初始化会话状态
if 'df_4g_preview' not in st.session_state: st.session_state.df_4g_preview = None; 
if 'df_5g_preview' not in st.session_state: st.session_state.df_5g_preview = None
if 'search_name' not in st.session_state: st.session_state.search_name = ""

# 加载全部数据用于预览
if uploaded_4g_file and st.session_state.df_4g_preview is None:
    try:
        st.session_state.df_4g_preview = pd.read_excel(uploaded_4g_file)
    except Exception as e:
        st.error(f"读取4G文件预览时出错：{e}")
        st.session_state.df_4g_preview = None

if uploaded_5g_file and st.session_state.df_5g_preview is None:
    try:
        st.session_state.df_5g_preview = pd.read_excel(uploaded_5g_file)
    except Exception as e:
        st.error(f"读取5G文件预览时出错：{e}")
        st.session_state.df_5g_preview = None

# 显示数据预览
if st.session_state.df_4g_preview is not None:
    display_paginated_dataframe(st.session_state.df_4g_preview, "4G数据预览")
if st.session_state.df_5g_preview is not None:
    display_paginated_dataframe(st.session_state.df_5g_preview, "5G数据预览")

# 初始化会话状态
if 'analysis_done' not in st.session_state:
    st.session_state.analysis_done = False
if 'search_name' not in st.session_state:
    st.session_state.search_name = ""
if 'df_4g' not in st.session_state:
    st.session_state.df_4g = None
if 'df_5g' not in st.session_state:
    st.session_state.df_5g = None
if 'results_df' not in st.session_state:
    st.session_state.results_df = None

# 分析和地图显示逻辑
if st.sidebar.button("🚀 开始分析", type="primary") or st.session_state.analysis_done:
    try:
        # 如果还没有完成分析，则执行分析
        if not st.session_state.analysis_done:
            # 检查是否上传了必要的文件
            if not uploaded_4g_file or not uploaded_5g_file:
                st.error("请先上传4G和5G小区工参表文件！")
                st.stop()
            
            with st.spinner("正在高效加载和验证数据..."):
                df_4g = load_and_validate_data(uploaded_4g_file, "4G")
                df_5g = load_and_validate_data(uploaded_5g_file, "5G")
            
            # 验证数据量是否合理
            if len(df_4g) == 0:
                st.error("4G数据文件中没有有效的数据行！")
                st.stop()
            
            progress_bar = st.progress(0, text="分析准备中...")
            
            def update_progress(current, total): 
                progress_bar.progress(current/total if total>0 else 0, text=f"正在分析: {current}/{total} 条记录...")
            
            results_df = analyze_5g_offload(df_4g, df_5g, d_colo, theta_colo, d_non_colo, n_non_colo, update_progress)
            progress_bar.progress(1.0, text="分析完成！正在准备结果展示...")
            
            # 保存数据到会话状态
            st.session_state.df_4g = df_4g
            st.session_state.df_5g = df_5g
            st.session_state.results_df = results_df
            st.session_state.analysis_done = True
        
        # 从会话状态中获取数据
        df_4g = st.session_state.df_4g
        df_5g = st.session_state.df_5g
        results_df = st.session_state.results_df
        
        # 显示分析结果，无论地图是否可用
        st.markdown("---"); st.subheader("📊 详细分析结果")
        st.dataframe(results_df, use_container_width=True)
        
        # 添加结果统计
        st.markdown("### 分析结果统计")
        total_4g = len(results_df)
        colo_offload = len(results_df[results_df['分析结果'].str.contains('共站址5G分流小区')])
        colo_tune = len(results_df[results_df['分析结果'].str.contains('共站址5G射频调优小区')])
        non_colo_offload = len(results_df[results_df['分析结果'].str.contains('非共站址5G分流小区')])
        need_construction = len(results_df[results_df['分析结果'].str.contains('5G规划建设')])
        
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1: st.metric("总4G小区数", total_4g)
        with col2: st.metric("共站址5G分流小区", colo_offload)
        with col3: st.metric("共站址射频调优小区", colo_tune)
        with col4: st.metric("非共站址5G分流小区", non_colo_offload)
        with col5: st.metric("需要5G规划建设小区", need_construction)
        
        # 添加地图搜索功能
        st.markdown("---")
        st.markdown("### 🔍 地图搜索")
        
        # 使用表单来处理搜索，确保地图会重新生成
        with st.form(key='search_form'):
            # 添加搜索输入框
            map_search_name = st.text_input(
                "请输入小区名称在地图上搜索：", 
                value=st.session_state.search_name
            )
            
            # 添加搜索按钮
            search_submitted = st.form_submit_button("🔍 在地图上搜索")
            
            # 当用户点击搜索按钮时，更新会话状态
            if search_submitted:
                st.session_state.search_name = map_search_name
        
        # 显示搜索状态
        if st.session_state.search_name:
            st.info(f"正在搜索包含 '{st.session_state.search_name}' 的小区...")
        
        # 生成Leaflet地图（统一的地图显示）
        st.markdown("---"); st.subheader("🗺️ Leaflet地图可视化结果")
        
        # 添加地图生成进度提示
        map_progress = st.progress(0)
        map_progress.text("正在准备地图数据...")
        
        try:
            # 限制数据量以提高性能
            map_progress.progress(20)
            map_progress.text("正在处理4G数据...")
            
            map_progress.progress(50)
            map_progress.text("正在处理数据...")
            
            # 调用地图生成函数，传递搜索名称
            map_obj = create_folium_map(df_4g, df_5g, results_df, None, st.session_state.search_name)
            
            map_progress.progress(100)
            map_progress.text("地图生成完成！")
            
            # 显示地图生成结果
            if isinstance(map_obj, str) and "地图生成过程中出错" in map_obj:
                st.error(map_obj)
            elif isinstance(map_obj, str) and "没有有效" in map_obj:
                st.warning(map_obj)
            else:
                # 使用folium_static显示地图对象
                from streamlit_folium import folium_static
                folium_static(map_obj, width=1600, height=1200)
        except Exception as e:
            st.error(f"地图生成过程中出错：{e}")
            # 显示详细的错误信息
            import traceback
            st.code(traceback.format_exc())
        finally:
            # 清理进度条
            map_progress.empty()
        
        output = BytesIO();
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            results_df.to_excel(writer, index=False, sheet_name='5G分流分析结果')
            # 添加统计信息到Excel
            workbook = writer.book
            stats_sheet = workbook.create_sheet('分析统计')
            stats_data = [
                ['统计项', '数量'],
                ['总4G小区数', total_4g],
                ['共站址5G分流小区', colo_offload],
                ['共站址射频调优小区', colo_tune],
                ['非共站址5G分流小区', non_colo_offload],
                ['需要5G规划建设小区', need_construction]
            ]
            for row in stats_data:
                stats_sheet.append(row)
        
        st.download_button("📥 下载分析结果", output.getvalue(), "5G分流分析结果.xlsx", "application/vnd.ms-excel")
            

        
    except ValueError as e:
        st.error(f"**数据加载或格式错误！**\n\n**错误详情**: {e}")
        st.info("请检查文件格式是否正确，确保包含所有必需的列：['小区名称', '经度', '纬度', '方位角']")
    except MemoryError:
        st.error("**内存不足错误！**\n\n文件过大，无法一次性处理。请尝试使用较小的文件或联系管理员增加服务器资源。")
    except Exception as e:
        st.error(f"**分析过程中出现意外错误！**\n\n**错误详情**: {type(e).__name__}: {e}")
        st.info("常见原因：\n1. 数据格式问题（如'经度'或'纬度'列包含非数字内容）\n2. 文件损坏或格式不正确\n3. 百度地图AK配置问题")
        
