"""
绕射损耗分析模型
"""
import numpy as np
from typing import List
from dataclasses import dataclass

from models.radar import RadarConfig
from models.turbine import Turbine
from models.target import TargetConfig
from models.results import DiffractionResult
from utils.geo_utils import calculate_distance, is_in_beam, is_blocking_path


class DiffractionModel:
    """绕射损耗分析模型"""
    
    def __init__(self):
        self.c = 299792458  # 光速 (m/s)
        self.earth_radius = 6371000  # 地球半径 (m)
    
    def calculate(self, radar: RadarConfig, turbines: List[Turbine],
                  target: TargetConfig = None) -> DiffractionResult:
        """
        计算绕射损耗

        Args:
            radar: 雷达配置
            turbines: 风机列表
            target: 目标配置（可选）

        Returns:
            DiffractionResult: 绕射损耗分析结果
        """
        if not turbines:
            return DiffractionResult()

        # 检查目标是否在波束内
        if target:
            target_in_beam, _, _ = is_in_beam(
                radar.latitude, radar.longitude,
                radar.altitude_m + radar.antenna_height_m,
                radar.beam_direction_deg, radar.beamwidth_deg,
                target.latitude, target.longitude, target.altitude_m,
                radar.max_range_km
            )
            # 如果目标不在波束内，不计算绕射损耗
            if not target_in_beam:
                return DiffractionResult(
                    knife_edge_loss=0.0,
                    fresnel_zone_clearance=0.0,
                    blockage_ratio=0.0,
                    main_lobe_distortion=0.0,
                    side_lobe_enhancement=0.0,
                    pattern_asymmetry=0.0,
                    effective_gain_loss=0.0,
                    terrain_shadowing=[]
                )

        # 初始化统计
        knife_edge_losses = []
        fresnel_zone_clearances = []
        blockage_ratios = []
        main_lobe_distortions = []
        side_lobe_enhancements = []
        pattern_asymmetries = []
        effective_gain_losses = []
        terrain_shadowing_data = []

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

            # 如果风机不在波束内，不产生绕射影响
            if not turbine_in_beam:
                continue

            # 检查风机是否在雷达和目标之间的路径上（绕射需要风机在视线路径上）
            if target:
                is_diffracting, _, _, _ = is_blocking_path(
                    radar.latitude, radar.longitude,
                    turbine.latitude, turbine.longitude,
                    target.latitude, target.longitude,
                    angular_tolerance=radar.beamwidth_deg / 2
                )

                # 如果风机不在绕射路径上，不产生绕射影响
                if not is_diffracting:
                    continue

            # 计算雷达-风机距离
            distance = calculate_distance(
                radar.latitude, radar.longitude,
                turbine.latitude, turbine.longitude
            )
            
            # 计算路径剖面参数
            radar_height = radar.antenna_height_m + radar.altitude_m
            turbine_height = turbine.tower_height_m + turbine.altitude_m
            
            # 计算障碍物高度（风机作为障碍物）
            obstacle_height = turbine_height
            
            # 计算菲涅尔区半径
            wavelength = radar.get_wavelength()
            fresnel_zone_radius = self._calculate_fresnel_zone_radius(distance, wavelength)
            
            # 计算菲涅尔区余隙（障碍物顶部到视距线的距离）
            # 简化：视距线高度随距离线性变化
            los_height_at_obstacle = radar_height + (turbine_height - radar_height) * 0.5
            fresnel_clearance = obstacle_height - los_height_at_obstacle
            fresnel_zone_clearances.append(fresnel_clearance)
            
            # 计算刃形绕射参数
            obstruction_parameter = self._calculate_obstruction_parameter(
                fresnel_clearance, fresnel_zone_radius
            )
            
            # 计算刃形绕射损耗
            knife_edge_loss = self._calculate_knife_edge_loss(obstruction_parameter)
            knife_edge_losses.append(knife_edge_loss)
            
            # 计算绕射遮挡比
            blockage_ratio = max(0, -fresnel_clearance / fresnel_zone_radius)
            blockage_ratios.append(blockage_ratio)
            
            # 计算主瓣畸变（基于绕射角）
            diffraction_angle = np.arctan(obstacle_height / distance)
            main_lobe_distortion = 20 * np.log10(1 + diffraction_angle)  # 简化模型
            main_lobe_distortions.append(main_lobe_distortion)
            
            # 计算副瓣增强（绕射导致副瓣电平提升）
            side_lobe_enhancement = 10 * np.log10(1 + blockage_ratio)
            side_lobe_enhancements.append(side_lobe_enhancement)
            
            # 计算方向图不对称度（绕射导致方向图不对称）
            pattern_asymmetry = abs(np.sin(diffraction_angle)) * 15  # 最大15dB不对称
            pattern_asymmetries.append(pattern_asymmetry)
            
            # 计算有效增益损失
            effective_gain_loss = knife_edge_loss + main_lobe_distortion
            effective_gain_losses.append(effective_gain_loss)
            
            # 记录地形遮蔽数据
            terrain_data = {
                'turbine_id': turbine.turbine_id,
                'turbine_name': turbine.name,
                'distance': distance,
                'obstacle_height': obstacle_height,
                'fresnel_zone_radius': fresnel_zone_radius,
                'fresnel_clearance': fresnel_clearance,
                'obstruction_parameter': obstruction_parameter,
                'knife_edge_loss': knife_edge_loss,
                'blockage_ratio': blockage_ratio
            }
            terrain_shadowing_data.append(terrain_data)
        
        # 返回综合结果
        return DiffractionResult(
            knife_edge_loss=np.mean(knife_edge_losses) if knife_edge_losses else 0,
            fresnel_zone_clearance=np.mean(fresnel_zone_clearances) if fresnel_zone_clearances else 0,
            blockage_ratio=np.mean(blockage_ratios) if blockage_ratios else 0,
            main_lobe_distortion=np.mean(main_lobe_distortions) if main_lobe_distortions else 0,
            side_lobe_enhancement=np.mean(side_lobe_enhancements) if side_lobe_enhancements else 0,
            pattern_asymmetry=np.mean(pattern_asymmetries) if pattern_asymmetries else 0,
            effective_gain_loss=np.mean(effective_gain_losses) if effective_gain_losses else 0,
            terrain_shadowing=terrain_shadowing_data
        )
    
    def _calculate_fresnel_zone_radius(self, distance: float, wavelength: float, 
                                       zone_order: int = 1) -> float:
        """
        计算第n阶菲涅尔区半径
        
        Args:
            distance: 总路径长度 (m)
            wavelength: 波长 (m)
            zone_order: 菲涅尔区阶数
            
        Returns:
            float: 菲涅尔区半径 (m)
        """
        # 对于路径中点处的菲涅尔区半径
        return np.sqrt(zone_order * wavelength * distance / 2)
    
    def _calculate_obstruction_parameter(self, clearance: float, 
                                         fresnel_zone_radius: float) -> float:
        """
        计算绕射障碍参数
        
        Args:
            clearance: 菲涅尔区余隙 (m)
            fresnel_zone_radius: 菲涅尔区半径 (m)
            
        Returns:
            float: 障碍参数ν
        """
        # 障碍参数ν = h / F1，其中h为余隙，F1为一阶菲涅尔区半径
        # 当ν>0时表示余隙为正（视线清晰），ν<0表示视线被遮挡
        return clearance / fresnel_zone_radius
    
    def _calculate_knife_edge_loss(self, obstruction_parameter: float) -> float:
        """
        计算刃形绕射损耗
        
        Args:
            obstruction_parameter: 障碍参数ν
            
        Returns:
            float: 绕射损耗 (dB)
        """
        # 使用标准的刃形绕射损耗公式
        if obstruction_parameter > 0:
            # 余隙为正，绕射损耗较小
            return 6.9 + 20 * np.log10(np.sqrt((obstruction_parameter - 0.1)**2 + 1) + obstruction_parameter - 0.1)
        else:
            # 余隙为负，绕射损耗较大
            return -20 * np.log10(0.5 - 0.62 * obstruction_parameter)
    
    def _calculate_earth_curvature(self, distance: float) -> float:
        """
        计算地球曲率引起的路径弯曲
        
        Args:
            distance: 距离 (m)
            
        Returns:
            float: 地球曲率高度 (m)
        """
        # 简化：地球曲率引起的路径下降
        return distance**2 / (8 * self.earth_radius)
    
    def _calculate_atmospheric_refraction(self, distance: float) -> float:
        """
        计算大气折射引起的路径弯曲
        
        Args:
            distance: 距离 (m)
            
        Returns:
            float: 大气折射高度修正 (m)
        """
        # 标准大气折射：等效地球半径 = 4/3 * 实际地球半径
        effective_earth_radius = self.earth_radius * 4 / 3
        return distance**2 / (2 * effective_earth_radius)