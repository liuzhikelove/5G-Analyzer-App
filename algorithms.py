# ===== File: algorithms.py =====

from haversine import haversine, Unit
import numpy as np

def calculate_distance(lat1, lon1, lat2, lon2):
    """
    使用haversine公式精确计算两个经纬度点之间的球面距离。
    此函数对应《计划书》第7页的"经纬度计算小区距离算法"。
    """
    try:
        point1 = (lat1, lon1)
        point2 = (lat2, lon2)
        return haversine(point1, point2, unit=Unit.METERS)
    except (ValueError, TypeError):
        return float('inf')


def calculate_azimuth_difference(azimuth1, azimuth2):
    """
    计算两个方位角(0-360度)之间的最小夹角。
    此函数对应《计划书》第9页中"共站方位夹角计算"的核心逻辑。
    """
    try:
        diff = abs(azimuth1 - azimuth2)
        return min(diff, 360 - diff)
    except (ValueError, TypeError):
        return float('inf')
    # ===== 这部分是需要被添加到 algorithms.py 文件末尾的代码 =====

import math

def create_sector_polygon(lon, lat, azimuth, radius_m, angle_deg):
    """
    根据中心点、方位角、半径和角度，生成扇形多边形的顶点坐标列表。

    参数:
        lon (float): 中心点经度
        lat (float): 中心点纬度
        azimuth (float): 方位角 (0-360度)
        radius_m (float): 扇区半径 (米)
        angle_deg (float): 扇区张开的角度 (例如 60 或 90度)

    返回:
        list: 一个包含扇形所有顶点坐标的列表，格式为 [[lon, lat], [lon, lat], ...]
    """
    # 地球半径（米）
    EARTH_RADIUS = 6378137.0
    
    # 将角度转换为弧度
    azimuth_rad = math.radians(azimuth)
    angle_rad = math.radians(angle_deg)
    
    # 计算扇区左右两边的起始和结束角度
    start_angle = azimuth_rad - angle_rad / 2
    end_angle = azimuth_rad + angle_rad / 2
    
    # 扇形弧上的点数量，越多越平滑
    steps = 20
    
    # 顶点列表，第一个点是中心点
    points = [[lon, lat]]
    
    # 计算弧上的所有点
    for i in range(steps + 1):
        # 当前角度
        current_angle = start_angle + (end_angle - start_angle) * i / steps
        
        # 将半径从米转换为经纬度偏移量
        lat_offset = (radius_m * math.cos(current_angle)) / EARTH_RADIUS
        lon_offset = (radius_m * math.sin(current_angle)) / (EARTH_RADIUS * math.cos(math.radians(lat)))
        
        # 计算新点的经纬度
        new_lat = lat + math.degrees(lat_offset)
        new_lon = lon + math.degrees(lon_offset)
        
        points.append([new_lon, new_lat])
        
    # 最后一个点也是中心点，形成闭合多边形
    points.append([lon, lat])
    
    return points
