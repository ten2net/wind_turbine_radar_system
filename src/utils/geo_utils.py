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


def is_in_beam(radar_lat: float, radar_lon: float, radar_height: float,
               radar_beam_direction: float, radar_beamwidth: float,
               target_lat: float, target_lon: float, target_height: float,
               max_range_km: float = 500.0) -> tuple:
    """
    检查目标是否在雷达波束范围内
    
    Args:
        radar_lat: 雷达纬度
        radar_lon: 雷达经度
        radar_height: 雷达高度（米）
        radar_beam_direction: 雷达波束中心方向（度，0=正北）
        radar_beamwidth: 雷达波束宽度（度）
        target_lat: 目标纬度
        target_lon: 目标经度
        target_height: 目标高度（米）
        max_range_km: 最大探测距离（km）
        
    Returns:
        (是否在波束内, 方位角差, 水平距离米)
    """
    # 计算水平距离
    distance = calculate_distance(radar_lat, radar_lon, target_lat, target_lon)
    
    # 检查距离是否在范围内
    if distance > max_range_km * 1000:
        return False, float('inf'), distance
    
    # 计算目标方位角
    bearing = calculate_bearing(radar_lat, radar_lon, target_lat, target_lon)
    
    # 计算方位角差（考虑0度跨越）
    angle_diff = abs(bearing - radar_beam_direction)
    angle_diff = min(angle_diff, 360 - angle_diff)
    
    # 检查是否在波束宽度一半以内
    in_beam = angle_diff <= radar_beamwidth / 2
    
    return in_beam, angle_diff, distance


def is_blocking_path(radar_lat: float, radar_lon: float,
                     turbine_lat: float, turbine_lon: float,
                     target_lat: float, target_lon: float,
                     angular_tolerance: float = 5.0) -> tuple:
    """
    检查风机是否在雷达和目标之间的遮挡路径上
    
    几何关系判断：
    - 只有当风机位于雷达-目标连线上（或附近），且距离雷达比目标近时，才会产生遮挡
    
    Args:
        radar_lat: 雷达纬度
        radar_lon: 雷达经度
        turbine_lat: 风机纬度
        turbine_lon: 风机经度
        target_lat: 目标纬度
        target_lon: 目标经度
        angular_tolerance: 角度容差（度），风机偏离雷达-目标连线的最大角度
        
    Returns:
        (是否产生遮挡, 雷达到风机距离, 雷达到目标距离, 偏离角度)
    """
    # 计算距离
    distance_rt = calculate_distance(radar_lat, radar_lon, turbine_lat, turbine_lon)
    distance_r2target = calculate_distance(radar_lat, radar_lon, target_lat, target_lon)
    
    # 如果风机比目标还远，不会遮挡目标
    if distance_rt >= distance_r2target:
        return False, distance_rt, distance_r2target, float('inf')
    
    # 计算方位角
    bearing_to_turbine = calculate_bearing(radar_lat, radar_lon, turbine_lat, turbine_lon)
    bearing_to_target = calculate_bearing(radar_lat, radar_lon, target_lat, target_lon)
    
    # 计算偏离角度
    angle_deviation = abs(bearing_to_turbine - bearing_to_target)
    angle_deviation = min(angle_deviation, 360 - angle_deviation)
    
    # 检查是否在容差范围内
    is_blocking = angle_deviation <= angular_tolerance
    
    return is_blocking, distance_rt, distance_r2target, angle_deviation
