# ===== File: map_generator.py (最终稳定算法版 v2.1) =====
import pandas as pd
from pyecharts import options as opts
from pyecharts.charts import BMap, Scatter, HeatMap
from pyecharts.globals import BMapType
import streamlit as st
import math
from algorithms import create_sector_polygon
class CoordinateConverter:
    def __init__(self): self.x_pi = 3.14159265358979324 * 3000.0 / 180.0; self.pi = 3.1415926535897932384626; self.a = 6378245.0; self.ee = 0.00669342162296594323
    def _transform_lat(self, lng, lat): ret = -100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat + 0.1 * lng * lat + 0.2 * math.sqrt(abs(lng)); ret += (20.0 * math.sin(6.0 * lng * self.pi) + 20.0 * math.sin(2.0 * lng * self.pi)) * 2.0 / 3.0; ret += (20.0 * math.sin(lat * self.pi) + 40.0 * math.sin(lat / 3.0 * self.pi)) * 2.0 / 3.0; ret += (160.0 * math.sin(lat / 12.0 * self.pi) + 320 * math.sin(lat * self.pi / 30.0)) * 2.0 / 3.0; return ret
    def _transform_lng(self, lng, lat): ret = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng + 0.1 * lng * lat + 0.1 * math.sqrt(abs(lng)); ret += (20.0 * math.sin(6.0 * lng * self.pi) + 20.0 * math.sin(2.0 * lng * self.pi)) * 2.0 / 3.0; ret += (20.0 * math.sin(lng * self.pi) + 40.0 * math.sin(lng / 3.0 * self.pi)) * 2.0 / 3.0; ret += (150.0 * math.sin(lng / 12.0 * self.pi) + 300.0 * math.sin(lng / 30.0 * self.pi)) * 2.0 / 3.0; return ret
    def wgs84_to_gcj02(self, lng, lat): dlat = self._transform_lat(lng - 105.0, lat - 35.0); dlng = self._transform_lng(lng - 105.0, lat - 35.0); radlat = lat / 180.0 * self.pi; magic = math.sin(radlat); magic = 1 - self.ee * magic * magic; sqrtmagic = math.sqrt(magic); dlat = (dlat * 180.0) / ((self.a * (1 - self.ee)) / (magic * sqrtmagic) * self.pi); dlng = (dlng * 180.0) / (self.a / sqrtmagic * math.cos(radlat) * self.pi); mglat = lat + dlat; mglng = lng + dlng; return [mglng, mglat]
    def gcj02_to_bd09(self, lng, lat): z = math.sqrt(lng * lng + lat * lat) + 0.00002 * math.sin(lat * self.x_pi); theta = math.atan2(lat, lng) + 0.000003 * math.cos(lng * self.x_pi); bd_lng = z * math.cos(theta) + 0.0065; bd_lat = z * math.sin(theta) + 0.006; return [bd_lng, bd_lat]
coord_converter = CoordinateConverter()
@st.cache_data
def convert_coords_for_baidu(_df):
    df = _df.copy(); 
    if df is None or df.empty: return pd.DataFrame()
    df['经度'] = pd.to_numeric(df['经度'], errors='coerce'); df['纬度'] = pd.to_numeric(df['纬度'], errors='coerce'); df.dropna(subset=['经度', '纬度'], inplace=True)
    if df.empty: return pd.DataFrame()
    converted_coords = []; failed_rows = 0
    for lon, lat in zip(df['经度'], df['纬度']):
        try:
            # 先检查经纬度是否有效
            if pd.isna(lon) or pd.isna(lat):
                failed_rows += 1
                converted_coords.append((None, None))
                continue
            
            # 尝试坐标转换，捕获所有可能的异常
            result1 = coord_converter.wgs84_to_gcj02(lon, lat)
            if result1 is None:
                failed_rows += 1
                converted_coords.append((None, None))
                continue
            gcj_lon, gcj_lat = result1
            
            result2 = coord_converter.gcj02_to_bd09(gcj_lon, gcj_lat)
            if result2 is None:
                failed_rows += 1
                converted_coords.append((None, None))
                continue
            bd_lon, bd_lat = result2
            
            converted_coords.append((bd_lon, bd_lat))
        except Exception as e: 
            failed_rows += 1
            converted_coords.append((None, None))
    if failed_rows > 0: st.warning(f"**数据警告**: 在坐标转换过程中，有 **{failed_rows}** 行数据因格式无效而被跳过。")
    df['b_lon'] = [c[0] for c in converted_coords]; df['b_lat'] = [c[1] for c in converted_coords]; df.dropna(subset=['b_lon', 'b_lat'], inplace=True)
    return df
def create_baidu_map(df_4g, df_5g, results_df, baidu_ak):
    try:
        df_4g_conv = convert_coords_for_baidu(df_4g); df_5g_conv = convert_coords_for_baidu(df_5g)
        if df_4g_conv.empty: return "没有有效的4G数据用于地图显示。"
        
        # 过滤掉可能导致问题的异常坐标
        df_4g_conv = df_4g_conv[(df_4g_conv['b_lon'] >= 73) & (df_4g_conv['b_lon'] <= 135) & 
                               (df_4g_conv['b_lat'] >= 18) & (df_4g_conv['b_lat'] <= 53)]
        df_5g_conv = df_5g_conv[(df_5g_conv['b_lon'] >= 73) & (df_5g_conv['b_lon'] <= 135) & 
                               (df_5g_conv['b_lat'] >= 18) & (df_5g_conv['b_lat'] <= 53)]
        
        if df_4g_conv.empty: return "没有有效的4G数据用于地图显示。"
        
        df_4g_vis = pd.merge(df_4g_conv, results_df[['小区名称', '分析结果']], on='小区名称', how='left')
        categories = {'共站址5G分流小区': [],'共站址5G射频调优小区': [],'非共站址5G分流小区': [],'5G规划建设': [],'其他': []}
        
        # 为每个类别添加数据，确保所有坐标都是有效的
        for _, r in df_4g_vis.iterrows():
            try:
                res = str(r.get('分析结果', '')); matched=False
                lon = r['b_lon']; lat = r['b_lat']
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
        
        # 过滤掉空的热力图数据
        heatmap_data_5g = []
        if not df_5g_conv.empty:
            for _, r in df_5g_conv.iterrows():
                try:
                    lon = r['b_lon']; lat = r['b_lat']
                    if pd.notna(lon) and pd.notna(lat) and 73 <= lon <= 135 and 18 <= lat <= 53:
                        heatmap_data_5g.append([lon, lat])  # 只添加经度和纬度，不添加权重
                except Exception as e:
                    continue
        
        # 计算中心坐标，使用中位数而不是均值，更稳健
        center_lon = df_4g_conv['b_lon'].median(); center_lat = df_4g_conv['b_lat'].median()
        
        # 创建地图对象
        bmap = (BMap(init_opts=opts.InitOpts(width="100%", height="600px"))
                .add_schema(baidu_ak=baidu_ak, center=[center_lon, center_lat], zoom=14, is_roam=True))
        
        color_map = {'共站址5G分流小区': '#28a745','共站址5G射频调优小区': '#ffc107','非共站址5G分流小区': '#17a2b8','5G规划建设': '#dc3545','其他': '#6c757d'}
        
        # 按分析结果分类生成扇区多边形
        sector_polygons_by_category = {category: [] for category in categories.keys()}
        
        # 遍历分析结果，为每个小区生成对应类别的扇区
        for _, r in df_4g_vis.iterrows():
            try:
                lon = r['b_lon']
                lat = r['b_lat']
                azimuth = r['方位角']
                analysis_result = r.get('分析结果', '')
                
                # 确定小区所属类别
                category = '其他'  # 默认类别
                for cat_key in categories.keys():
                    if cat_key in analysis_result:
                        category = cat_key
                        break
                
                # 确保坐标和方位角都是有效数值
                if pd.notna(lon) and pd.notna(lat) and pd.notna(azimuth):
                    # 生成扇形多边形，半径500米，角度60度
                    polygon = create_sector_polygon(lon, lat, azimuth, 500, 60)
                    sector_polygons_by_category[category].append(polygon)
            except Exception as e:
                continue
        
        # 为每个类别添加散点图，确保数据不为空
        for name, data in categories.items():
            if data and len(data) > 0:
                try:
                    bmap.add(series_name=name, type_="scatter", data_pair=data, 
                            symbol="pin", symbol_size=15, color=color_map.get(name), 
                            label_opts=opts.LabelOpts(is_show=False))
                except Exception as e:
                    continue
        
        # 添加热力图，确保数据不为空
        if heatmap_data_5g and len(heatmap_data_5g) > 0:
            try:
                # 使用散点图模拟热力图效果
                bmap.add(series_name="5G站点热力图", type_="scatter", 
                        data_pair=heatmap_data_5g, 
                        symbol="circle", 
                        symbol_size=10, 
                        color="#ff6b6b",
                        label_opts=opts.LabelOpts(is_show=False),
                        itemstyle_opts=opts.ItemStyleOpts(opacity=0.6))
            except Exception as e:
                st.warning(f"热力图添加失败: {str(e)}")
        
        # 添加扇区图层，使用line类型绘制多边形
        for category, polygons in sector_polygons_by_category.items():
            if polygons and len(polygons) > 0:
                for i, polygon in enumerate(polygons):
                    if polygon and len(polygon) > 2:
                        try:
                            # 使用line类型绘制扇区的边界和填充
                            bmap.add(series_name=f"{category}_扇区", type_="line", 
                                    data_pair=polygon, 
                                    symbol="none", 
                                    is_polyline=True, 
                                    line_opts=opts.LineOpts(color=color_map.get(category), opacity=0.7, width=2),
                                    area_opts=opts.AreaOpts(color=color_map.get(category), opacity=0.2))
                        except Exception as e:
                            continue
        
        # 设置全局配置
        bmap.set_global_opts(
            title_opts=opts.TitleOpts(title="小区分析结果百度地图可视化", pos_left="center"),
            legend_opts=opts.LegendOpts(orient="vertical", pos_top="10%", pos_left="2%"),
            tooltip_opts=opts.TooltipOpts(
                trigger="item", 
                formatter=lambda p: f"{p.seriesName}<br/>经度: {p.data[0]:.6f}<br/>纬度: {p.data[1]:.6f}" if p and p.data else ""
            )
        )
        
        return bmap.render_embed()
    except Exception as e:
        return f"地图生成过程中出错：{str(e)}"
