"""
散射分析模型
"""
import numpy as np
from typing import List

from models.radar import RadarConfig
from models.turbine import Turbine
from models.target import TargetConfig
from models.results import ScatteringResult


class ScatteringModel:
    """散射分析模型"""
    
    # 物理常数
    C = 299792458  # 光速 (m/s)
    K_BOLTZMANN = 1.38e-23  # 玻尔兹曼常数
    T0 = 290  # 标准温度 (K)
    
    def __init__(self, system_loss_db: float = 3.0):
        self.system_loss_db = system_loss_db
        self.system_loss_linear = 10 ** (system_loss_db / 10)
    
    def calculate(self, radar: RadarConfig, turbines: List[Turbine], 
                  target: TargetConfig) -> ScatteringResult:
        """
        计算散射干扰
        
        Args:
            radar: 雷达配置
            turbines: 风机列表
            target: 目标配置
            
        Returns:
            ScatteringResult: 散射分析结果
        """
        if not turbines:
            return ScatteringResult()
        
        # 计算波长
        wavelength = self.C / (radar.frequency_ghz * 1e9)
        
        # 计算目标距离（假设目标在雷达最大探测距离处，3度仰角）
        target_distance = target.altitude_m / np.tan(np.radians(3))
        target_distance = min(target_distance, radar.max_range_km * 1000)
        
        # 计算目标回波功率
        target_power = self._calculate_radar_return(
            radar, target.rcs_dbsm, target_distance, wavelength
        )
        
        # 计算各风机干扰功率
        turbine_powers = []
        total_interference = 0.0
        
        for turbine in turbines:
            distance = self._calculate_distance(radar, turbine)
            power = self._calculate_radar_return(
                radar, turbine.rcs_dbsm, distance, wavelength
            )
            
            turbine_powers.append({
                'turbine_id': turbine.turbine_id,
                'turbine_name': turbine.name,
                'distance_km': round(distance / 1000, 2),
                'rcs_dbsm': turbine.rcs_dbsm,
                'power_dbm': round(power, 2)
            })
            
            # 非相干叠加（功率相加）
            total_interference += 10 ** (power / 10)
        
        # 总干扰功率
        interference_dbm = 10 * np.log10(total_interference) if total_interference > 0 else -200
        
        # 计算信干比
        sjr = target_power - interference_dbm
        
        # 计算信干比恶化（假设无干扰时SJR为20dB）
        sjr_degradation = max(0, 20 - sjr)
        
        # 计算距离剖面
        range_profile = self._calculate_range_profile(radar, turbines, wavelength)
        
        return ScatteringResult(
            interference_power=round(interference_dbm, 2),
            target_power=round(target_power, 2),
            sjr=round(sjr, 2),
            sjr_degradation=round(sjr_degradation, 2),
            affected_turbines=turbine_powers,
            range_profile=range_profile
        )
    
    def _calculate_radar_return(self, radar: RadarConfig, rcs_dbsm: float, 
                                distance: float, wavelength: float) -> float:
        """计算雷达回波功率 (dBm)"""
        # 雷达方程
        # P_r = P_t * G^2 * λ^2 * σ / ((4π)^3 * R^4 * L)
        
        # 转换为线性单位
        pt_linear = radar.power_kw * 1000  # W
        g_linear = 10 ** (radar.antenna_gain_dbi / 10)
        rcs_linear = 10 ** (rcs_dbsm / 10)
        
        # 计算接收功率
        numerator = pt_linear * (g_linear ** 2) * (wavelength ** 2) * rcs_linear
        denominator = ((4 * np.pi) ** 3) * (max(distance, 1) ** 4) * self.system_loss_linear
        
        pr_linear = numerator / denominator
        
        # 转换为dBm
        pr_dbm = 10 * np.log10(pr_linear * 1000)
        
        return pr_dbm
    
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
    
    def _calculate_range_profile(self, radar: RadarConfig, turbines: List[Turbine], 
                                  wavelength: float, num_points: int = 100) -> List[float]:
        """计算距离剖面干扰"""
        max_range = radar.max_range_km * 1000
        ranges = np.linspace(1000, max_range, num_points)
        profile = []
        
        for r in ranges:
            # 计算该距离处的总干扰
            total_power = 0.0
            for turbine in turbines:
                distance = self._calculate_distance(radar, turbine)
                # 只考虑距离分辨率范围内的风机
                if abs(distance - r) < radar.range_resolution_m:
                    power = self._calculate_radar_return(
                        radar, turbine.rcs_dbsm, distance, wavelength
                    )
                    total_power += 10 ** (power / 10)
            
            profile_dbm = 10 * np.log10(total_power) if total_power > 0 else -200
            profile.append(round(profile_dbm, 2))
        
        return profile
