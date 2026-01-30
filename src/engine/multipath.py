"""
多径效应分析模型
"""
import numpy as np
from typing import List
from dataclasses import dataclass

from models.radar import RadarConfig
from models.turbine import Turbine
from models.target import TargetConfig
from models.results import MultipathResult
from utils.geo_utils import calculate_distance, is_in_beam, is_blocking_path


class MultipathModel:
    """多径效应分析模型"""
    
    def __init__(self):
        self.c = 299792458  # 光速 (m/s)
        self.fresnel_zone_order = 1  # 菲涅尔区阶数
    
    def calculate(self, radar: RadarConfig, turbines: List[Turbine],
                  target: TargetConfig = None) -> MultipathResult:
        """
        计算多径效应

        Args:
            radar: 雷达配置
            turbines: 风机列表
            target: 目标配置（可选）

        Returns:
            MultipathResult: 多径效应分析结果
        """
        if not turbines:
            return MultipathResult()

        # 检查目标是否在波束内
        if target:
            target_in_beam, _, _ = is_in_beam(
                radar.latitude, radar.longitude,
                radar.altitude_m + radar.antenna_height_m,
                radar.beam_direction_deg, radar.beamwidth_deg,
                target.latitude, target.longitude, target.altitude_m,
                radar.max_range_km
            )
            # 如果目标不在波束内，不计算多径效应
            if not target_in_beam:
                return MultipathResult(
                    peak_to_null_ratio=0.0,
                    fading_depth=0.0,
                    fading_frequency=0.0,
                    multipath_distance=0.0,
                    delay_spread=0.0,
                    constructive_count=0,
                    destructive_count=0,
                    pattern_distortion=0.0,
                    phase_shift_deg=0.0
                )

        # 初始化统计
        peak_to_null_ratios = []
        fading_depths = []
        fading_frequencies = []
        multipath_distances = []
        delay_spreads = []
        constructive_count = 0
        destructive_count = 0
        pattern_distortions = []
        phase_shifts = []

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

            # 如果风机不在波束内，不产生多径效应
            if not turbine_in_beam:
                continue

            # 检查风机是否在雷达和目标之间的路径上（多径效应主要来自路径上的风机）
            if target:
                is_multipath, _, _, _ = is_blocking_path(
                    radar.latitude, radar.longitude,
                    turbine.latitude, turbine.longitude,
                    target.latitude, target.longitude,
                    angular_tolerance=radar.beamwidth_deg
                )

                # 如果风机不在多径路径上，不产生显著多径效应
                if not is_multipath:
                    continue

            # 计算直接路径距离
            direct_distance = calculate_distance(
                radar.latitude, radar.longitude,
                turbine.latitude, turbine.longitude
            )
            
            # 计算反射路径距离（假设地面反射）
            # 简化模型：反射路径 = 直接路径 + 额外路径长度
            reflection_distance = direct_distance * 1.2  # 简化：反射路径比直接路径长20%
            
            # 计算路径差
            delta_distance = reflection_distance - direct_distance
            multipath_distances.append(delta_distance)
            
            # 计算相位差（弧度）
            wavelength = radar.get_wavelength()
            delta_phase = 2 * np.pi * delta_distance / wavelength
            
            # 转换为角度
            phase_shift = np.degrees(delta_phase) % 360
            phase_shifts.append(phase_shift)
            
            # 计算合成信号幅度（假设反射系数为0.3）
            reflection_coeff = 0.3
            amplitude_direct = 1.0
            amplitude_reflected = reflection_coeff
            
            # 计算合成幅度（同相和正交分量）
            in_phase = amplitude_direct + amplitude_reflected * np.cos(delta_phase)
            quad_phase = amplitude_reflected * np.sin(delta_phase)
            composite_amplitude = np.sqrt(in_phase**2 + quad_phase**2)
            
            # 计算峰谷比
            max_amplitude = amplitude_direct + amplitude_reflected
            min_amplitude = abs(amplitude_direct - amplitude_reflected)
            peak_to_null_ratio = 20 * np.log10(max_amplitude / min_amplitude) if min_amplitude > 0 else 60
            peak_to_null_ratios.append(peak_to_null_ratio)
            
            # 计算衰落深度
            fading_depth = 20 * np.log10(max_amplitude / composite_amplitude)
            fading_depths.append(fading_depth)
            
            # 计算衰落频率（假设目标移动速度）
            if target is not None:
                # 简化：衰落频率与目标速度和波长相关
                doppler_freq = 2 * target.velocity_ms / wavelength
                fading_frequency = doppler_freq * 0.1  # 简化系数
            else:
                fading_frequency = 0.5  # 默认值 (Hz)
            fading_frequencies.append(fading_frequency)
            
            # 计算时延扩展
            delay_spread = delta_distance / self.c * 1e9  # 转换为纳秒
            delay_spreads.append(delay_spread)
            
            # 统计同相/反相叠加
            if np.cos(delta_phase) > 0.7:  # 相位差接近0度
                constructive_count += 1
            elif np.cos(delta_phase) < -0.7:  # 相位差接近180度
                destructive_count += 1
            
            # 计算方向图畸变（简化模型）
            pattern_distortion = abs(np.sin(delta_phase)) * 30  # 最大30度畸变
            pattern_distortions.append(pattern_distortion)
        
        # 返回综合结果
        return MultipathResult(
            peak_to_null_ratio=np.mean(peak_to_null_ratios) if peak_to_null_ratios else 0,
            fading_depth=np.mean(fading_depths) if fading_depths else 0,
            fading_frequency=np.mean(fading_frequencies) if fading_frequencies else 0,
            multipath_distance=np.mean(multipath_distances) if multipath_distances else 0,
            delay_spread=np.mean(delay_spreads) if delay_spreads else 0,
            constructive_count=constructive_count,
            destructive_count=destructive_count,
            pattern_distortion=np.mean(pattern_distortions) if pattern_distortions else 0,
            phase_shift_deg=np.mean(phase_shifts) if phase_shifts else 0
        )
    
    def _calculate_reflection_path(self, radar: RadarConfig, turbine: Turbine, 
                                   ground_height: float = 0.0) -> float:
        """
        计算地面反射路径长度
        
        Args:
            radar: 雷达配置
            turbine: 风机配置
            ground_height: 地面海拔高度 (m)
            
        Returns:
            float: 反射路径长度 (m)
        """
        # 简化模型：使用镜像法计算反射路径
        radar_height = radar.antenna_height_m + radar.altitude_m
        turbine_height = turbine.tower_height_m + turbine.altitude_m
        
        # 计算水平距离
        horizontal_distance = calculate_distance(
            radar.latitude, radar.longitude,
            turbine.latitude, turbine.longitude
        )
        
        # 计算直接路径
        direct_path = np.sqrt(horizontal_distance**2 + (turbine_height - radar_height)**2)
        
        # 计算反射路径（通过镜像点）
        reflected_path = np.sqrt(horizontal_distance**2 + (turbine_height + radar_height)**2)
        
        return reflected_path
    
    def _calculate_fresnel_zone_radius(self, distance: float, wavelength: float, 
                                       zone_order: int = 1) -> float:
        """
        计算菲涅尔区半径
        
        Args:
            distance: 总路径长度 (m)
            wavelength: 波长 (m)
            zone_order: 菲涅尔区阶数
            
        Returns:
            float: 菲涅尔区半径 (m)
        """
        return np.sqrt(zone_order * wavelength * distance)