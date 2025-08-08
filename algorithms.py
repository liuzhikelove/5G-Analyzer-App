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