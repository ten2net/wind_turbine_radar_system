"""
遮挡分析模型
"""
import numpy as np
from typing import List

from models.radar import RadarConfig
from models.turbine import Turbine
from models.target import TargetConfig
from models.results import BlockingResult


class BlockingModel:
    """遮挡分析模型"""
    
    def __init__(self):
        self.sector_resolution = 1.0  # 扇区分辨率(度)
    
    def calculate(self, radar: RadarConfig, turbines: List[Turbine], 
                  target: TargetConfig = None) -> BlockingResult:
        """
        计算遮挡效应
        
        Args:
            radar: 雷达配置
            turbines: 风机列表
            target: 目标配置（可选）
            
        Returns:
            BlockingResult: 遮挡分析结果
        """
        if not turbines:
            return BlockingResult()
        
        total_blocking = 0.0
        max_blocking = 0.0
        all_sectors = []
        
        for turbine in turbines:
            # 计算雷达-风机距离
            distance = self._calculate_distance(radar, turbine)
            
            # 计算投影面积
            proj_area = self._calculate_projection(radar, turbine, distance)
            
            # 计算波束截面积
            beam_area = self._calculate_beam_area(radar, distance)
            
            # 计算遮挡因子
            blocking = min(proj_area / beam_area, 1.0) * 100 if beam_area > 0 else 0
            
            # 计算遮挡持续时间
            duration = self._calculate_blocking_duration(turbine, radar, distance)
            
            # 确定受影响扇区
            sector = self._calculate_affected_sector(radar, turbine)
            
            total_blocking += blocking
            max_blocking = max(max_blocking, blocking)
            all_sectors.append({
                'turbine_id': turbine.turbine_id,
                'turbine_name': turbine.name,
                'blocking': round(blocking, 2),
                'duration': round(duration, 2),
                'sector': sector,
                'distance_km': round(distance / 1000, 2)
            })
        
        # 计算时域遮挡序列（一个旋转周期）
        time_series = self._calculate_time_series(turbines, radar)
        
        # 取最后一个风机的投影和波束面积作为代表
        last_proj_area = self._calculate_projection(radar, turbines[-1], 
                         self._calculate_distance(radar, turbines[-1])) if turbines else 0
        last_beam_area = self._calculate_beam_area(radar, 
                         self._calculate_distance(radar, turbines[-1])) if turbines else 1
        
        return BlockingResult(
            blocking_factor=min(total_blocking, 100.0),
            blocking_duration=max_blocking,
            projection_area=round(last_proj_area, 2),
            beam_area=round(last_beam_area, 2),
            affected_sectors=all_sectors,
            time_series=time_series
        )
    
    def _calculate_distance(self, radar: RadarConfig, turbine: Turbine) -> float:
        """计算雷达-风机距离（米）"""
        # 使用Haversine公式计算水平距离
        R = 6371000  # 地球半径(米)
        lat1, lon1 = np.radians(radar.latitude), np.radians(radar.longitude)
        lat2, lon2 = np.radians(turbine.latitude), np.radians(turbine.longitude)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
        c = 2 * np.arcsin(np.sqrt(a))
        horizontal_distance = R * c
        
        # 计算斜距
        height_diff = (turbine.altitude_m + turbine.tower_height_m) - \
                      (radar.altitude_m + radar.antenna_height_m)
        slant_range = np.sqrt(horizontal_distance**2 + height_diff**2)
        
        return slant_range
    
    def _calculate_projection(self, radar: RadarConfig, turbine: Turbine, 
                             distance: float) -> float:
        """计算风机投影面积"""
        # 计算视线仰角
        height_diff = (turbine.altitude_m + turbine.tower_height_m) - \
                      (radar.altitude_m + radar.antenna_height_m)
        elevation = np.arctan2(height_diff, 
                              np.sqrt(max(0, distance**2 - height_diff**2)))
        
        # 塔筒投影（视为圆柱体）
        tower_height = turbine.tower_height_m
        tower_diameter = turbine.tower_diameter_m
        tower_proj = tower_height * tower_diameter * np.abs(np.cos(elevation))
        
        # 叶片投影（简化模型：叶片在旋转平面内的投影）
        blade_length = turbine.blade_length_m
        blade_width = blade_length * 0.1  # 假设叶片宽度为长度的10%
        blade_proj = turbine.blade_count * blade_length * blade_width
        
        # 总投影（考虑叶片旋转的平均效果）
        total_proj = tower_proj + blade_proj * 0.5
        
        return total_proj
    
    def _calculate_beam_area(self, radar: RadarConfig, distance: float) -> float:
        """计算雷达波束截面积"""
        # 3dB波束宽度转换为弧度
        beamwidth_rad = np.radians(radar.beamwidth_deg)
        
        # 波束半径
        beam_radius = distance * np.tan(beamwidth_rad / 2)
        
        # 波束截面积
        beam_area = np.pi * beam_radius**2
        
        return max(beam_area, 1.0)  # 避免除零
    
    def _calculate_blocking_duration(self, turbine: Turbine, radar: RadarConfig, 
                                     distance: float) -> float:
        """计算遮挡持续时间占比"""
        # 叶片在视线方向的角宽度
        blade_width = turbine.blade_length_m * 0.1
        angular_width = np.arctan(blade_width / max(distance, 1))
        
        # 旋转周期（秒）
        rotation_period = 60.0 / max(turbine.rotation_speed_rpm, 1)
        
        # 单个叶片遮挡时间
        single_blade_time = angular_width / (2 * np.pi) * rotation_period
        
        # 总遮挡时间（一个周期内）
        total_block_time = turbine.blade_count * single_blade_time
        
        # 遮挡持续时间占比
        duration_ratio = (total_block_time / rotation_period) * 100
        
        return duration_ratio
    
    def _calculate_affected_sector(self, radar: RadarConfig, 
                                   turbine: Turbine) -> dict:
        """计算受影响扇区"""
        # 计算相对方位角
        delta_lon = turbine.longitude - radar.longitude
        delta_lat = turbine.latitude - radar.latitude
        
        bearing = np.degrees(np.arctan2(delta_lon, delta_lat))
        bearing = (bearing + 360) % 360
        
        # 扇区范围（考虑波束宽度）
        sector_width = radar.beamwidth_deg
        sector_start = (bearing - sector_width / 2) % 360
        sector_end = (bearing + sector_width / 2) % 360
        
        return {
            'center': round(bearing, 2),
            'start': round(sector_start, 2),
            'end': round(sector_end, 2),
            'width': round(sector_width, 2)
        }
    
    def _calculate_time_series(self, turbines: List[Turbine], 
                               radar: RadarConfig, num_points: int = 100) -> List[float]:
        """计算时域遮挡序列"""
        if not turbines:
            return []
        
        time_series = []
        max_rpm = max(t.rotation_speed_rpm for t in turbines)
        rotation_period = 60.0 / max_rpm if max_rpm > 0 else 60
        
        for i in range(num_points):
            t = i / num_points * rotation_period
            blocking = 0.0
            
            for turbine in turbines:
                # 计算当前时刻叶片角度
                angle = 2 * np.pi * t * turbine.rotation_speed_rpm / 60
                
                # 计算投影面积（随角度变化）
                blade_factor = np.abs(np.cos(angle))
                blocking += blade_factor
            
            avg_blocking = blocking / len(turbines) if turbines else 0
            time_series.append(round(min(avg_blocking * 100, 100), 2))
        
        return time_series
