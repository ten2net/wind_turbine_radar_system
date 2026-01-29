"""
地理计算工具函数
"""
import numpy as np


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    使用Haversine公式计算两点间距离
    
    Args:
        lat1: 点1纬度
        lon1: 点1经度
        lat2: 点2纬度
        lon2: 点2经度
        
    Returns:
        距离（米）
    """
    R = 6371000  # 地球半径(米)
    
    lat1_rad = np.radians(lat1)
    lat2_rad = np.radians(lat2)
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    
    a = np.sin(dlat/2)**2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    
    return R * c


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    计算从点1到点2的方位角
    
    Args:
        lat1: 点1纬度
        lon1: 点1经度
        lat2: 点2纬度
        lon2: 点2经度
        
    Returns:
        方位角（度，0-360）
    """
    lat1_rad = np.radians(lat1)
    lat2_rad = np.radians(lat2)
    dlon = np.radians(lon2 - lon1)
    
    x = np.sin(dlon) * np.cos(lat2_rad)
    y = np.cos(lat1_rad) * np.sin(lat2_rad) - np.sin(lat1_rad) * np.cos(lat2_rad) * np.cos(dlon)
    
    bearing = np.degrees(np.arctan2(x, y))
    bearing = (bearing + 360) % 360
    
    return bearing


def calculate_destination(lat: float, lon: float, bearing: float, 
                         distance: float) -> tuple:
    """
    计算从某点出发，沿某方位角走某距离后的目的地坐标
    
    Args:
        lat: 起始纬度
        lon: 起始经度
        bearing: 方位角（度）
        distance: 距离（米）
        
    Returns:
        (纬度, 经度)
    """
    R = 6371000
    
    lat_rad = np.radians(lat)
    lon_rad = np.radians(lon)
    bearing_rad = np.radians(bearing)
    
    lat2_rad = np.arcsin(np.sin(lat_rad) * np.cos(distance/R) + 
                         np.cos(lat_rad) * np.sin(distance/R) * np.cos(bearing_rad))
    lon2_rad = lon_rad + np.arctan2(np.sin(bearing_rad) * np.sin(distance/R) * np.cos(lat_rad),
                                    np.cos(distance/R) - np.sin(lat_rad) * np.sin(lat2_rad))
    
    return np.degrees(lat2_rad), np.degrees(lon2_rad)


def calculate_elevation_angle(radar_height: float, target_height: float, 
                              distance: float) -> float:
    """
    计算仰角
    
    Args:
        radar_height: 雷达高度（米）
        target_height: 目标高度（米）
        distance: 水平距离（米）
        
    Returns:
        仰角（度）
    """
    height_diff = target_height - radar_height
    return np.degrees(np.arctan2(height_diff, distance))
