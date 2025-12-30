# ===== File: map_generator.py (最终稳定算法版 v2.1) =====
import pandas as pd; from pyecharts import options as opts; from pyecharts.charts import BMap, Scatter, HeatMap; from pyecharts.globals import BMapType; import streamlit as st; import math
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
        try: gcj_lon, gcj_lat = coord_converter.wgs84_to_gcj02(lon, lat); bd_lon, bd_lat = coord_converter.gcj02_to_bd09(gcj_lon, gcj_lat); converted_coords.append((bd_lon, bd_lat))
        except (ValueError, TypeError): failed_rows += 1; converted_coords.append((None, None))
    if failed_rows > 0: st.warning(f"**数据警告**: 在坐标转换过程中，有 **{failed_rows}** 行数据因格式无效而被跳过。")
    df['b_lon'] = [c[0] for c in converted_coords]; df['b_lat'] = [c[1] for c in converted_coords]; df.dropna(subset=['b_lon', 'b_lat'], inplace=True)
    return df
def create_baidu_map(df_4g, df_5g, results_df, baidu_ak):
    df_4g_conv = convert_coords_for_baidu(df_4g); df_5g_conv = convert_coords_for_baidu(df_5g)
    if df_4g_conv.empty: return "没有有效的4G数据用于地图显示。"
    df_4g_vis = pd.merge(df_4g_conv, results_df[['小区名称', '分析结果']], on='小区名称', how='left')
    categories = {'共站址5G分流小区': [],'共站址5G射频调优小区': [],'非共站址5G分流小区': [],'5G规划建设': [],'其他': []}
    for _, r in df_4g_vis.iterrows():
        res = str(r.get('分析结果', '')); matched=False
        for k in categories.keys():
            if k in res: categories[k].append([r['b_lon'], r['b_lat'], r['小区名称']]); matched=True; break
        if not matched: categories['其他'].append([r['b_lon'], r['b_lat'], r['小区名称']])
    heatmap_data_5g = [[r['b_lon'], r['b_lat'], 1] for _, r in df_5g_conv.iterrows()] if not df_5g_conv.empty else []
    center_lon = df_4g_conv['b_lon'].mean(); center_lat = df_4g_conv['b_lat'].mean()
    bmap = (BMap(init_opts=opts.InitOpts(width="100%", height="600px")).add_schema(baidu_ak=baidu_ak, center=[center_lon, center_lat], zoom=14, is_roam=True))
    color_map = {'共站址5G分流小区': '#28a745','共站址5G射频调优小区': '#ffc107','非共站址5G分流小区': '#17a2b8','5G规划建设': '#dc3545','其他': '#6c757d'}
    for name, data in categories.items():
        if data: bmap.add(series_name=name, type_="scatter", data_pair=data, symbol="pin", symbol_size=15, color=color_map.get(name), label_opts=opts.LabelOpts(is_show=False))
    if heatmap_data_5g: bmap.add(series_name="5G站点热力图", type_="heatmap", data_pair=heatmap_data_5g, point_size=5, blur_size=15)
    bmap.set_global_opts(title_opts=opts.TitleOpts(title="小区分析结果百度地图可视化", pos_left="center"), legend_opts=opts.LegendOpts(orient="vertical", pos_top="10%", pos_left="2%"), tooltip_opts=opts.TooltipOpts(trigger="item", formatter=lambda p: f"{p.seriesName}<br/>{p.data.value[2]}" if p.data else ""))
    return bmap.render_embed()