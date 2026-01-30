"""
精度偏差分析模型
"""
import numpy as np
from typing import List

from models.radar import RadarConfig
from models.turbine import Turbine
from models.target import TargetConfig
from models.results import AccuracyResult
from utils.geo_utils import is_in_beam, is_blocking_path


class AccuracyModel:
    """精度分析模型"""
    
    C = 299792458  # 光速 (m/s)
    
    def __init__(self, scattering_model=None):
        from .scattering import ScatteringModel
        self.scattering_model = scattering_model or ScatteringModel()
    
    def calculate(self, radar: RadarConfig, turbines: List[Turbine],
                  target: TargetConfig) -> AccuracyResult:
        """
        计算精度偏差

        Args:
            radar: 雷达配置
            turbines: 风机列表
            target: 目标配置

        Returns:
            AccuracyResult: 精度分析结果
        """
        if not turbines:
            return AccuracyResult()

        # 检查目标是否在波束内
        target_in_beam, _, _ = is_in_beam(
            radar.latitude, radar.longitude,
            radar.altitude_m + radar.antenna_height_m,
            radar.beam_direction_deg, radar.beamwidth_deg,
            target.latitude, target.longitude, target.altitude_m,
            radar.max_range_km
        )

        # 如果目标不在波束内，不计算精度偏差
        if not target_in_beam:
            return AccuracyResult(
                angle_error=0.0,
                range_error=0.0,
                velocity_error=0.0,
                angle_degradation=0.0,
                range_degradation=0.0,
                velocity_degradation=0.0,
                overall_degradation=0.0
            )

        # 获取散射干扰数据
        scattering = self.scattering_model.calculate(radar, turbines, target)
        
        # 计算测角偏差
        angle_err = self._calculate_angle_error(radar, scattering)
        
        # 计算测距偏差
        range_err = self._calculate_range_error(radar, turbines, target)
        
        # 计算测速偏差
        velocity_err = self._calculate_velocity_error(radar, turbines, target)
        
        # 计算精度降级比例
        angle_deg = (angle_err / max(radar.angle_resolution_deg, 0.1)) * 100
        range_deg = (range_err / max(radar.range_resolution_m, 1)) * 100
        
        # 速度分辨率（简化）
        wavelength = self.C / (radar.frequency_ghz * 1e9)
        velocity_resolution = (wavelength * radar.prf_hz) / (2 * 100)  # 假设100个多普勒滤波器
        velocity_deg = (velocity_err / max(velocity_resolution, 0.1)) * 100
        
        # 综合降级等级
        overall = np.sqrt(angle_deg**2 + range_deg**2 + velocity_deg**2) / np.sqrt(3)
        
        return AccuracyResult(
            angle_error=round(angle_err, 3),
            range_error=round(range_err, 2),
            velocity_error=round(velocity_err, 2),
            angle_degradation=min(round(angle_deg, 2), 100),
            range_degradation=min(round(range_deg, 2), 100),
            velocity_degradation=min(round(velocity_deg, 2), 100),
            overall_degradation=min(round(overall, 2), 100)
        )
    
    def _calculate_angle_error(self, radar, scattering) -> float:
        """计算测角偏差"""
        # Δθ = θ_3dB × √(P_turbine / P_target)
        sjr_linear = 10 ** (scattering.sjr / 10)
        interference_ratio = 1 / sjr_linear if sjr_linear > 0 else 0
        
        angle_error = radar.beamwidth_deg * np.sqrt(interference_ratio)
        
        # 添加随机相位影响（简化）
        angle_error *= (1 + 0.3 * np.random.random())
        
        return angle_error
    
    def _calculate_range_error(self, radar, turbines, target) -> float:
        """计算测距偏差（多径效应）"""
        max_error = 0.0
        
        for turbine in turbines:
            # 检查风机是否在雷达波束范围内
            turbine_in_beam, _, _ = is_in_beam(
                radar.latitude, radar.longitude,
                radar.altitude_m + radar.antenna_height_m,
                radar.beam_direction_deg, radar.beamwidth_deg,
                turbine.latitude, turbine.longitude,
                turbine.altitude_m + turbine.tower_height_m,
                radar.max_range_km
            )
            
            # 如果风机不在波束内，不产生多径效应
            if not turbine_in_beam:
                continue
            
            # 检查风机是否在雷达和目标之间的路径上（多径效应主要来自路径上的风机）
            is_multipath, _, _, _ = is_blocking_path(
                radar.latitude, radar.longitude,
                turbine.latitude, turbine.longitude,
                target.latitude, target.longitude,
                angular_tolerance=radar.beamwidth_deg
            )
            
            # 如果风机不在多径路径上，不产生显著多径效应
            if not is_multipath:
                continue
            
            # 计算多径距离
            distance_rt = self._calculate_distance(radar, turbine)
            
            # 简化：假设目标在雷达-风机延长线上
            # 多径距离 = 雷达-风机距离 + 风机-目标距离
            distance_tt = target.altitude_m / np.tan(np.radians(3))  # 目标距离
            multipath_distance = distance_rt + distance_tt
            
            # 直达距离
            direct_distance = distance_tt
            
            # 距离差
            delta_r = abs(multipath_distance - direct_distance)
            
            # 转换为时延误差
            delta_tau = delta_r / self.C
            
            # 距离测量误差（简化模型）
            range_error = (self.C * delta_tau) / 2
            
            max_error = max(max_error, range_error)
        
        return min(max_error, radar.range_resolution_m * 2)
    
    def _calculate_velocity_error(self, radar, turbines, target) -> float:
        """计算测速偏差"""
        # 基于多普勒频移误差
        from .doppler import DopplerModel
        doppler_model = DopplerModel()
        doppler = doppler_model.calculate(radar, turbines, target)
        
        wavelength = self.C / (radar.frequency_ghz * 1e9)
        
        # 速度误差 = 多普勒误差 × 波长 / 2
        velocity_error = (doppler.doppler_bandwidth * wavelength) / 2
        
        return velocity_error
    
    def _calculate_distance(self, radar: RadarConfig, turbine: Turbine) -> float:
        """计算雷达-风机距离"""
        R = 6371000
        lat1, lon1 = np.radians(radar.latitude), np.radians(radar.longitude)
        lat2, lon2 = np.radians(turbine.latitude), np.radians(turbine.longitude)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
        c = 2 * np.arcsin(np.sqrt(a))
        horizontal_distance = R * c
        
        height_diff = (turbine.altitude_m + turbine.tower_height_m) - \
                      (radar.altitude_m + radar.antenna_height_m)
        slant_range = np.sqrt(horizontal_distance**2 + height_diff**2)
        
        return slant_range
