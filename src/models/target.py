"""
目标配置模型
"""
from dataclasses import dataclass, field
from typing import Optional


# 预设目标类型
TARGET_TYPES = {
    "民航客机": {
        "rcs_dbsm": 10.0,
        "altitude_m": 10000.0,
        "velocity_ms": 250.0
    },
    "小型飞机": {
        "rcs_dbsm": 5.0,
        "altitude_m": 3000.0,
        "velocity_ms": 100.0
    },
    "战斗机": {
        "rcs_dbsm": 0.0,
        "altitude_m": 10000.0,
        "velocity_ms": 600.0
    },
    "隐身战机": {
        "rcs_dbsm": -20.0,
        "altitude_m": 12000.0,
        "velocity_ms": 700.0
    },
    "巡航导弹": {
        "rcs_dbsm": -10.0,
        "altitude_m": 100.0,
        "velocity_ms": 300.0
    },
    "小型无人机": {
        "rcs_dbsm": -15.0,
        "altitude_m": 500.0,
        "velocity_ms": 30.0
    },
    "直升机": {
        "rcs_dbsm": 3.0,
        "altitude_m": 1000.0,
        "velocity_ms": 80.0
    },
    "自定义": {
        "rcs_dbsm": 10.0,
        "altitude_m": 5000.0,
        "velocity_ms": 200.0
    }
}


@dataclass
class TargetConfig:
    """目标配置类"""
    
    # 基本参数
    target_type: str = "民航客机"         # 目标类型
    rcs_dbsm: float = 10.0                # 目标RCS(dBm²)
    altitude_m: float = 10000.0           # 飞行高度(m)
    velocity_ms: float = 250.0            # 飞行速度(m/s)
    
    # 位置参数
    latitude: float = 39.9142             # 纬度
    longitude: float = 120.5074           # 经度
    
    # 可选参数
    heading_deg: float = 0.0              # 航向角(度)
    climb_rate_ms: float = 0.0            # 爬升率(m/s)
    
    def __post_init__(self):
        """参数验证"""
        self.rcs_dbsm = max(-30.0, min(50.0, self.rcs_dbsm))
        self.altitude_m = max(0.0, min(30000.0, self.altitude_m))
        self.velocity_ms = max(0.0, min(1000.0, self.velocity_ms))
    
    @classmethod
    def from_type(cls, target_type: str, **kwargs) -> 'TargetConfig':
        """从预设类型创建目标"""
        if target_type not in TARGET_TYPES:
            target_type = "自定义"
        
        type_data = TARGET_TYPES[target_type].copy()
        type_data['target_type'] = target_type
        type_data.update(kwargs)
        
        return cls(**type_data)
    
    @staticmethod
    def get_available_types() -> list:
        """获取可用目标类型列表"""
        return list(TARGET_TYPES.keys())
    
    @staticmethod
    def get_type_params(target_type: str) -> dict:
        """获取类型参数"""
        return TARGET_TYPES.get(target_type, TARGET_TYPES["自定义"]).copy()
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'target_type': self.target_type,
            'rcs_dbsm': self.rcs_dbsm,
            'altitude_m': self.altitude_m,
            'velocity_ms': self.velocity_ms,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'heading_deg': self.heading_deg,
            'climb_rate_ms': self.climb_rate_ms
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'TargetConfig':
        """从字典创建"""
        return cls(
            target_type=data.get('target_type', '民航客机'),
            rcs_dbsm=data.get('rcs_dbsm', 10.0),
            altitude_m=data.get('altitude_m', 10000.0),
            velocity_ms=data.get('velocity_ms', 250.0),
            latitude=data.get('latitude', 39.9142),
            longitude=data.get('longitude', 120.5074),
            heading_deg=data.get('heading_deg', 0.0),
            climb_rate_ms=data.get('climb_rate_ms', 0.0)
        )
