"""
风电场目标圆周运动仿真模块
目标以风电场中心为圆心，以指定半径做圆周运动
"""
import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from datetime import datetime
import math

from utils.geo_utils import calculate_distance, calculate_bearing, calculate_destination


@dataclass
class CircularMotionConfig:
    """圆周运动配置"""
    center_lat: float = 39.9042          # 圆心纬度（风电场中心）
    center_lon: float = 120.4074         # 圆心经度
    radius_inner_km: float = 1.0         # 内圈半径（km）
    radius_outer_km: float = 5.0         # 外圈半径（km）
    velocity_ms: float = 100.0           # 目标速度（m/s）
    altitude_m: float = 1000.0           # 飞行高度（m）
    rcs_dbsm: float = 10.0               # 目标RCS（dBm²）
    target_type: str = "小型飞机"         # 目标类型
    
    # 仿真参数
    time_step_ms: float = 100.0          # 时间步长（ms）
    update_interval_ms: float = 500.0    # 更新间隔（ms）


@dataclass
class TargetState:
    """目标状态"""
    latitude: float
    longitude: float
    altitude_m: float
    heading_deg: float
    velocity_ms: float
    distance_to_radar_m: float
    bearing_from_radar_deg: float
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class DetectionMetrics:
    """探测指标"""
    detection_probability: float          # 探测概率（0-1）
    snr_db: float                         # 信噪比（dB）
    range_error_m: float                  # 测距误差（m）
    angle_error_deg: float                # 测角误差（度）
    is_blocked: bool                      # 是否被遮挡
    blocked_by: List[str] = field(default_factory=list)  # 遮挡风机列表


class CircularMotionSimulator:
    """圆周运动仿真器"""
    
    def __init__(self, config: CircularMotionConfig, radar, turbines):
        """
        初始化仿真器
        
        Args:
            config: 圆周运动配置
            radar: 雷达配置对象
            turbines: 风机列表
        """
        self.config = config
        self.radar = radar
        self.turbines = turbines
        
        # 当前角度（弧度）
        self.current_angle_inner = 0.0
        self.current_angle_outer = np.pi  # 外圈目标与内圈目标相对
        
        # 仿真状态
        self.is_running = False
        self.current_time_ms = 0.0
        
        # 历史数据
        self.target_trajectory_inner: List[TargetState] = []
        self.target_trajectory_outer: List[TargetState] = []
        self.metrics_history_inner: List[DetectionMetrics] = []
        self.metrics_history_outer: List[DetectionMetrics] = []
    
    def reset(self):
        """重置仿真"""
        self.current_angle_inner = 0.0
        self.current_angle_outer = np.pi
        self.current_time_ms = 0.0
        self.is_running = False
        self.target_trajectory_inner.clear()
        self.target_trajectory_outer.clear()
        self.metrics_history_inner.clear()
        self.metrics_history_outer.clear()
    
    def update(self, delta_time_ms: float) -> Tuple[Optional[TargetState], Optional[TargetState]]:
        """
        更新仿真状态
        
        Args:
            delta_time_ms: 时间增量（ms）
            
        Returns:
            (inner_state, outer_state): 内外圈目标状态
        """
        if not self.is_running:
            return None, None
        
        self.current_time_ms += delta_time_ms
        
        # 计算角速度（弧度/ms）
        angular_velocity_inner = (self.config.velocity_ms / (self.config.radius_inner_km * 1000)) * (delta_time_ms / 1000)
        angular_velocity_outer = (self.config.velocity_ms / (self.config.radius_outer_km * 1000)) * (delta_time_ms / 1000)
        
        # 更新角度
        self.current_angle_inner += angular_velocity_inner
        self.current_angle_outer += angular_velocity_outer
        
        # 归一化到0-2π
        self.current_angle_inner = self.current_angle_inner % (2 * np.pi)
        self.current_angle_outer = self.current_angle_outer % (2 * np.pi)
        
        # 计算目标位置
        inner_state = self._calculate_target_state(
            self.current_angle_inner, 
            self.config.radius_inner_km,
            "内圈"
        )
        outer_state = self._calculate_target_state(
            self.current_angle_outer, 
            self.config.radius_outer_km,
            "外圈"
        )
        
        # 保存轨迹
        self.target_trajectory_inner.append(inner_state)
        self.target_trajectory_outer.append(outer_state)
        
        # 限制历史数据长度
        max_history = 1000
        if len(self.target_trajectory_inner) > max_history:
            self.target_trajectory_inner.pop(0)
        if len(self.target_trajectory_outer) > max_history:
            self.target_trajectory_outer.pop(0)
        
        return inner_state, outer_state
    
    def _calculate_target_state(self, angle_rad: float, radius_km: float, label: str) -> TargetState:
        """计算目标状态"""
        # 计算目标位置（从圆心出发，按角度和半径计算）
        # 将极坐标转换为笛卡尔坐标，再转换为经纬度
        
        # 计算目标相对于圆心的偏移（km）
        # 0度为正北，顺时针增加
        dx = radius_km * np.sin(angle_rad)  # 东西方向
        dy = radius_km * np.cos(angle_rad)  # 南北方向
        
        # 转换为经纬度偏移（近似）
        # 1度纬度 ≈ 111 km
        # 1度经度 ≈ 111 * cos(纬度) km
        lat_offset = dy / 111.0
        lon_offset = dx / (111.0 * np.cos(np.radians(self.config.center_lat)))
        
        target_lat = self.config.center_lat + lat_offset
        target_lon = self.config.center_lon + lon_offset
        
        # 计算航向角（运动方向）
        # 圆周运动的切线方向
        heading_deg = np.degrees(angle_rad + np.pi / 2) % 360
        
        # 计算与雷达的距离和方位
        distance_to_radar = calculate_distance(
            self.radar.latitude, self.radar.longitude,
            target_lat, target_lon
        )
        bearing_from_radar = calculate_bearing(
            self.radar.latitude, self.radar.longitude,
            target_lat, target_lon
        )
        
        return TargetState(
            latitude=target_lat,
            longitude=target_lon,
            altitude_m=self.config.altitude_m,
            heading_deg=heading_deg,
            velocity_ms=self.config.velocity_ms,
            distance_to_radar_m=distance_to_radar,
            bearing_from_radar_deg=bearing_from_radar
        )
    
    def calculate_detection_metrics(self, target_state: TargetState) -> DetectionMetrics:
        """
        计算探测指标
        
        Args:
            target_state: 目标状态
            
        Returns:
            DetectionMetrics: 探测指标
        """
        # 检查是否在雷达覆盖范围内
        max_range_m = self.radar.max_range_km * 1000
        distance_m = target_state.distance_to_radar_m
        
        if distance_m > max_range_m:
            return DetectionMetrics(
                detection_probability=0.0,
                snr_db=-999.0,
                range_error_m=0.0,
                angle_error_deg=0.0,
                is_blocked=False
            )
        
        # 检查是否在波束范围内
        bearing = target_state.bearing_from_radar_deg
        beam_center = self.radar.beam_direction_deg
        beam_width = self.radar.beamwidth_deg
        
        angle_diff = abs(bearing - beam_center)
        angle_diff = min(angle_diff, 360 - angle_diff)
        
        if angle_diff > beam_width / 2:
            # 在波束范围外
            return DetectionMetrics(
                detection_probability=0.0,
                snr_db=-999.0,
                range_error_m=0.0,
                angle_error_deg=0.0,
                is_blocked=False
            )
        
        # 检查是否被风机遮挡
        is_blocked, blocked_by = self._check_blocking(target_state)
        
        # 计算信噪比（简化模型）
        # 雷达方程：SNR ∝ (Pt * G^2 * λ^2 * σ) / (R^4 * k * T * B * F * L)
        # 这里使用简化模型
        wavelength = self.radar.get_wavelength()
        
        # 基础SNR计算
        snr_base = (self.radar.power_kw * 1000 * 
                   (10 ** (self.radar.antenna_gain_dbi / 10)) ** 2 * 
                   wavelength ** 2 * 
                   (10 ** (self.config.rcs_dbsm / 10))) / \
                   (distance_m ** 4)
        
        # 转换为dB
        snr_db = 10 * np.log10(snr_base) + 100  # 偏移量使数值合理
        
        # 考虑遮挡影响
        if is_blocked:
            snr_db -= 20.0  # 遮挡导致SNR下降20dB
        
        # 考虑波束方向图影响
        beam_factor = np.exp(-2.776 * (angle_diff / (beam_width / 2)) ** 2)
        snr_db += 10 * np.log10(beam_factor)
        
        # 计算探测概率（基于SNR）
        # 简化模型：SNR > 13dB时，探测概率接近1
        if snr_db > 20:
            detection_probability = 0.99
        elif snr_db > 13:
            detection_probability = 0.9 + (snr_db - 13) / 70
        elif snr_db > 0:
            detection_probability = 0.5 + snr_db / 26
        elif snr_db > -10:
            detection_probability = max(0, 0.1 + snr_db / 100)
        else:
            detection_probability = 0.0
        
        # 计算测距误差（与SNR相关）
        range_error_m = 50.0 / max(1, 10 ** (snr_db / 20))
        
        # 计算测角误差（与SNR和波束宽度相关）
        angle_error_deg = (self.radar.beamwidth_deg / (2 * np.sqrt(2))) / max(1, 10 ** (snr_db / 20))
        
        return DetectionMetrics(
            detection_probability=detection_probability,
            snr_db=snr_db,
            range_error_m=range_error_m,
            angle_error_deg=angle_error_deg,
            is_blocked=is_blocked,
            blocked_by=blocked_by
        )
    
    def _check_blocking(self, target_state: TargetState) -> Tuple[bool, List[str]]:
        """
        检查目标是否被风机遮挡
        
        Args:
            target_state: 目标状态
            
        Returns:
            (is_blocked, blocked_by): 是否被遮挡，遮挡风机列表
        """
        blocked_by = []
        
        # 计算目标相对于雷达的方位角
        target_bearing = target_state.bearing_from_radar_deg
        
        for turbine in self.turbines:
            # 计算风机相对于雷达的方位角
            turbine_bearing = calculate_bearing(
                self.radar.latitude, self.radar.longitude,
                turbine.latitude, turbine.longitude
            )
            
            # 计算方位角差
            angle_diff = abs(target_bearing - turbine_bearing)
            angle_diff = min(angle_diff, 360 - angle_diff)
            
            # 如果方位角差小于阈值，认为被遮挡
            # 阈值基于风机距离和大小
            turbine_distance = calculate_distance(
                self.radar.latitude, self.radar.longitude,
                turbine.latitude, turbine.longitude
            )
            
            # 简化的遮挡判断：方位角差小于2度且风机在目标和雷达之间
            if angle_diff < 2.0:
                # 检查风机是否在目标和雷达之间
                if turbine_distance < target_state.distance_to_radar_m:
                    blocked_by.append(turbine.name)
        
        return len(blocked_by) > 0, blocked_by
    
    def start(self):
        """开始仿真"""
        self.is_running = True
    
    def stop(self):
        """停止仿真"""
        self.is_running = False
    
    def get_trajectory_data(self) -> Tuple[List[dict], List[dict]]:
        """
        获取轨迹数据（用于地图显示）
        
        Returns:
            (inner_data, outer_data): 内外圈轨迹数据
        """
        inner_data = [
            {
                'lat': state.latitude,
                'lon': state.longitude,
                'altitude': state.altitude_m,
                'heading': state.heading_deg,
                'distance_to_radar': state.distance_to_radar_m / 1000,  # km
                'timestamp': state.timestamp.isoformat()
            }
            for state in self.target_trajectory_inner
        ]
        
        outer_data = [
            {
                'lat': state.latitude,
                'lon': state.longitude,
                'altitude': state.altitude_m,
                'heading': state.heading_deg,
                'distance_to_radar': state.distance_to_radar_m / 1000,  # km
                'timestamp': state.timestamp.isoformat()
            }
            for state in self.target_trajectory_outer
        ]
        
        return inner_data, outer_data
    
    def get_current_positions(self) -> Tuple[Optional[dict], Optional[dict]]:
        """
        获取当前位置
        
        Returns:
            (inner_pos, outer_pos): 内外圈当前位置
        """
        if not self.target_trajectory_inner or not self.target_trajectory_outer:
            return None, None
        
        inner = self.target_trajectory_inner[-1]
        outer = self.target_trajectory_outer[-1]
        
        inner_metrics = self.calculate_detection_metrics(inner)
        outer_metrics = self.calculate_detection_metrics(outer)
        
        inner_pos = {
            'lat': inner.latitude,
            'lon': inner.longitude,
            'altitude': inner.altitude_m,
            'heading': inner.heading_deg,
            'distance_to_radar_km': inner.distance_to_radar_m / 1000,
            'bearing_from_radar_deg': inner.bearing_from_radar_deg,
            'detection_probability': inner_metrics.detection_probability,
            'snr_db': inner_metrics.snr_db,
            'is_blocked': inner_metrics.is_blocked,
            'blocked_by': inner_metrics.blocked_by,
            'label': '内圈目标 (1km)'
        }
        
        outer_pos = {
            'lat': outer.latitude,
            'lon': outer.longitude,
            'altitude': outer.altitude_m,
            'heading': outer.heading_deg,
            'distance_to_radar_km': outer.distance_to_radar_m / 1000,
            'bearing_from_radar_deg': outer.bearing_from_radar_deg,
            'detection_probability': outer_metrics.detection_probability,
            'snr_db': outer_metrics.snr_db,
            'is_blocked': outer_metrics.is_blocked,
            'blocked_by': outer_metrics.blocked_by,
            'label': '外圈目标 (5km)'
        }
        
        return inner_pos, outer_pos
