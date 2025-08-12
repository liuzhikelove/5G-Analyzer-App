# ===== File: algorithms.py (最终正确版) =====
# 版本确认：此文件已包含扇区生成函数

from haversine import haversine, Unit
import numpy as np
import math

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


def create_sector_polygon(lon, lat, azimuth, radius_m, angle_deg):
    """
    根据中心点、方位角、半径和角度，生成扇形多边形的顶点坐标列表。
    """
    EARTH_RADIUS = 6378137.0
    azimuth_rad = math.radians(azimuth)
    angle_rad = math.radians(angle_deg)
    start_angle = azimuth_rad - angle_rad / 2
    end_angle = azimuth_rad + angle_rad / 2
    steps = 20
    points = [[lon, lat]]
    for i in range(steps + 1):
        current_angle = start_angle + (end_angle - start_angle) * i / steps
        lat_offset = (radius_m * math.cos(current_angle)) / EARTH_RADIUS
        lon_offset = (radius_m * math.sin(current_angle)) / (EARTH_RADIUS * math.cos(math.radians(lat)))
        new_lat = lat + math.degrees(lat_offset)
        new_lon = lon + math.degrees(lon_offset)
        points.append([new_lon, new_lat])
    points.append([lon, lat])
    return points
