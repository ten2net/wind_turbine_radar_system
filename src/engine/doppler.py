"""
多普勒分析模型
"""
import numpy as np
from typing import List

from models.radar import RadarConfig
from models.turbine import Turbine
from models.target import TargetConfig
from models.results import DopplerResult
from utils.geo_utils import is_in_beam, is_blocking_path


class DopplerModel:
    """多普勒分析模型"""
    
    C = 299792458  # 光速 (m/s)
    
    def calculate(self, radar: RadarConfig, turbines: List[Turbine],
                  target: TargetConfig) -> DopplerResult:
        """
        计算多普勒效应

        Args:
            radar: 雷达配置
            turbines: 风机列表
            target: 目标配置

        Returns:
            DopplerResult: 多普勒分析结果
        """
        if not turbines:
            return DopplerResult()

        # 检查目标是否在波束内
        target_in_beam, _, _ = is_in_beam(
            radar.latitude, radar.longitude,
            radar.altitude_m + radar.antenna_height_m,
            radar.beam_direction_deg, radar.beamwidth_deg,
            target.latitude, target.longitude, target.altitude_m,
            radar.max_range_km
        )

        # 如果目标不在波束内，多普勒干扰不影响目标检测
        if not target_in_beam:
            return DopplerResult(
                max_doppler_shift=0.0,
                doppler_bandwidth=0.0,
                affected_filters=[],
                mti_degradation=0.0,
                spectrum_data={'frequencies': [], 'amplitude': [], 'prf': radar.prf_hz},
                velocity_spread=0.0
            )

        max_shift = 0.0
        max_bandwidth = 0.0
        max_velocity = 0.0

        for turbine in turbines:
            # 检查风机是否在波束内
            turbine_in_beam, _, _ = is_in_beam(
                radar.latitude, radar.longitude,
                radar.altitude_m + radar.antenna_height_m,
                radar.beam_direction_deg, radar.beamwidth_deg,
                turbine.latitude, turbine.longitude,
                turbine.altitude_m + turbine.tower_height_m,
                radar.max_range_km
            )

            # 如果风机不在波束内，不产生多普勒干扰
            if not turbine_in_beam:
                continue

            # 检查风机是否在雷达和目标之间的路径上
            is_interfering, _, _, _ = is_blocking_path(
                radar.latitude, radar.longitude,
                turbine.latitude, turbine.longitude,
                target.latitude, target.longitude,
                angular_tolerance=radar.beamwidth_deg
            )

            # 如果风机不在干扰路径上，对目标的多普勒干扰较小
            if not is_interfering:
                continue

            # 计算叶片尖端速度
            tip_velocity = self._calculate_tip_velocity(turbine)

            # 计算多普勒频移
            doppler_shift = self._calculate_doppler_shift(
                tip_velocity, radar.frequency_ghz
            )

            # 计算多普勒带宽（叶片速度范围）
            doppler_bw = doppler_shift  # 从0到最大值

            # 计算速度展宽
            velocity_spread = tip_velocity

            max_shift = max(max_shift, doppler_shift)
            max_bandwidth = max(max_bandwidth, doppler_bw)
            max_velocity = max(max_velocity, velocity_spread)
        
        # 确定受影响的滤波器
        affected_filters = self._determine_affected_filters(
            max_shift, max_bandwidth, radar
        )
        
        # 计算MTI改善因子恶化
        mti_deg = self._calculate_mti_degradation(radar, turbines)
        
        # 生成频谱数据
        spectrum = self._generate_spectrum(radar, turbines)
        
        return DopplerResult(
            max_doppler_shift=round(max_shift, 2),
            doppler_bandwidth=round(max_bandwidth, 2),
            affected_filters=affected_filters,
            mti_degradation=round(mti_deg, 2),
            spectrum_data=spectrum,
            velocity_spread=round(max_velocity, 2)
        )
    
    def _calculate_tip_velocity(self, turbine: Turbine) -> float:
        """计算叶片尖端线速度 (m/s)"""
        # v = ω × r = 2π × n × r / 60
        angular_velocity = 2 * np.pi * turbine.rotation_speed_rpm / 60
        tip_velocity = angular_velocity * turbine.blade_length_m
        return tip_velocity
    
    def _calculate_doppler_shift(self, velocity: float, frequency_ghz: float) -> float:
        """计算多普勒频移 (Hz)"""
        # f_d = 2 × v × f₀ / c
        frequency_hz = frequency_ghz * 1e9
        doppler_shift = 2 * velocity * frequency_hz / self.C
        return doppler_shift
    
    def _determine_affected_filters(self, max_shift: float, bandwidth: float, 
                                    radar: RadarConfig) -> List[str]:
        """确定受影响的滤波器类型"""
        affected = []
        
        # 计算多普勒滤波器组参数
        prf = radar.prf_hz
        doppler_resolution = prf  # 简化模型
        
        # 判断影响的滤波器
        if bandwidth > doppler_resolution * 0.1:
            affected.append("MTI滤波器")
        
        if max_shift > prf / 2:
            affected.append("距离模糊滤波器")
        
        if bandwidth > prf * 0.5:
            affected.append("所有多普勒滤波器")
        
        if not affected:
            affected.append("无明显影响")
        
        return affected
    
    def _calculate_mti_degradation(self, radar: RadarConfig, 
                                   turbines: List[Turbine]) -> float:
        """计算MTI改善因子恶化"""
        # 简化模型：基于风机数量和转速计算
        total_degradation = 0.0
        
        for turbine in turbines:
            # 转速越高，多普勒效应越严重
            speed_factor = turbine.rotation_speed_rpm / 30.0  # 归一化到30rpm
            degradation = speed_factor * 2.0  # 每台风机最多贡献2dB恶化
            total_degradation += degradation
        
        return min(total_degradation, 20.0)  # 最大恶化20dB
    
    def _generate_spectrum(self, radar: RadarConfig, turbines: List[Turbine], 
                           num_points: int = 200) -> dict:
        """生成多普勒频谱"""
        prf = radar.prf_hz
        frequencies = np.linspace(-prf/2, prf/2, num_points).tolist()
        spectrum = np.zeros(num_points)
        
        for turbine in turbines:
            tip_velocity = self._calculate_tip_velocity(turbine)
            max_shift = self._calculate_doppler_shift(tip_velocity, radar.frequency_ghz)
            
            # 生成叶片微多普勒特征（简化模型）
            for i, f in enumerate(frequencies):
                if abs(f) <= max_shift:
                    # 叶片旋转产生的频谱特征（高斯分布）
                    spectrum[i] += np.exp(-(f**2) / (2 * (max_shift/3)**2))
        
        # 归一化
        if np.max(spectrum) > 0:
            spectrum = spectrum / np.max(spectrum)
        
        return {
            'frequencies': frequencies,
            'amplitude': spectrum.tolist(),
            'prf': prf
        }
