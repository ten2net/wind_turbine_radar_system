"""
风机配置模型
"""
from dataclasses import dataclass, field
from typing import Optional
import uuid


# 预设风机型号
TURBINE_MODELS = {
    "自定义": {
        "tower_height_m": 80.0,
        "blade_length_m": 50.0,
        "blade_count": 3,
        "rotation_speed_rpm": 15.0,
        "tower_diameter_m": 4.0,
        "rcs_dbsm": 40.0,
        "rated_power_mw": 2.0
    },
    "Vestas V90": {
        "tower_height_m": 105.0,
        "blade_length_m": 45.0,
        "blade_count": 3,
        "rotation_speed_rpm": 16.0,
        "tower_diameter_m": 4.5,
        "rcs_dbsm": 42.0,
        "rated_power_mw": 3.0
    },
    "GE Haliade-X": {
        "tower_height_m": 150.0,
        "blade_length_m": 107.0,
        "blade_count": 3,
        "rotation_speed_rpm": 8.5,
        "tower_diameter_m": 6.0,
        "rcs_dbsm": 48.0,
        "rated_power_mw": 12.0
    },
    "金风GW155": {
        "tower_height_m": 100.0,
        "blade_length_m": 77.0,
        "blade_count": 3,
        "rotation_speed_rpm": 12.0,
        "tower_diameter_m": 5.0,
        "rcs_dbsm": 45.0,
        "rated_power_mw": 6.0
    },
    "明阳MySE8.0": {
        "tower_height_m": 120.0,
        "blade_length_m": 90.0,
        "blade_count": 3,
        "rotation_speed_rpm": 10.0,
        "tower_diameter_m": 5.5,
        "rcs_dbsm": 47.0,
        "rated_power_mw": 8.0
    },
    "西门子SG 14-236 DD": {
        "tower_height_m": 140.0,
        "blade_length_m": 118.0,
        "blade_count": 3,
        "rotation_speed_rpm": 7.5,
        "tower_diameter_m": 6.5,
        "rcs_dbsm": 49.0,
        "rated_power_mw": 14.0
    }
}


@dataclass
class Turbine:
    """风机配置类"""
    
    # 基本参数
    name: str = "风机"
    model: str = "自定义"
    tower_height_m: float = 80.0        # 塔筒高度(m)
    blade_length_m: float = 50.0        # 叶片长度(m)
    blade_count: int = 3                # 叶片数量
    rotation_speed_rpm: float = 15.0    # 转速(rpm)
    tower_diameter_m: float = 4.0       # 塔筒直径(m)
    rcs_dbsm: float = 40.0              # RCS(dBm²)
    material: str = "金属"               # 材料类型
    rated_power_mw: float = 2.0         # 额定功率(MW)
    
    # 位置参数
    latitude: float = 39.9142           # 纬度
    longitude: float = 119.5974         # 经度
    altitude_m: float = 0.0             # 海拔高度(m)
    yaw_angle_deg: float = 0.0          # 偏航角(度)
    
    # 系统标识
    turbine_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    
    def __post_init__(self):
        """参数验证"""
        self.tower_height_m = max(20.0, min(200.0, self.tower_height_m))
        self.blade_length_m = max(10.0, min(120.0, self.blade_length_m))
        self.blade_count = max(2, min(5, self.blade_count))
        self.rotation_speed_rpm = max(5.0, min(30.0, self.rotation_speed_rpm))
        self.rcs_dbsm = max(10.0, min(60.0, self.rcs_dbsm))
    
    @classmethod
    def from_model(cls, model_name: str, **kwargs) -> 'Turbine':
        """从预设型号创建风机"""
        if model_name not in TURBINE_MODELS:
            model_name = "自定义"
        
        model_data = TURBINE_MODELS[model_name].copy()
        model_data['model'] = model_name
        model_data.update(kwargs)
        
        return cls(**model_data)
    
    @staticmethod
    def get_available_models() -> list:
        """获取可用型号列表"""
        return list(TURBINE_MODELS.keys())
    
    @staticmethod
    def get_model_params(model_name: str) -> dict:
        """获取型号参数"""
        return TURBINE_MODELS.get(model_name, TURBINE_MODELS["自定义"]).copy()
    
    def get_tip_velocity(self) -> float:
        """获取叶片尖端线速度(m/s)"""
        # v = ω × r = 2π × n × r / 60
        angular_velocity = 2 * 3.14159 * self.rotation_speed_rpm / 60
        return angular_velocity * self.blade_length_m
    
    def get_rotor_swept_area(self) -> float:
        """获取叶轮扫风面积(m²)"""
        import math
        return math.pi * (self.blade_length_m ** 2)
    
    def get_total_height(self) -> float:
        """获取总高度(m)"""
        return self.tower_height_m + self.blade_length_m
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'turbine_id': self.turbine_id,
            'name': self.name,
            'model': self.model,
            'tower_height_m': self.tower_height_m,
            'blade_length_m': self.blade_length_m,
            'blade_count': self.blade_count,
            'rotation_speed_rpm': self.rotation_speed_rpm,
            'tower_diameter_m': self.tower_diameter_m,
            'rcs_dbsm': self.rcs_dbsm,
            'material': self.material,
            'rated_power_mw': self.rated_power_mw,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'altitude_m': self.altitude_m,
            'yaw_angle_deg': self.yaw_angle_deg
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Turbine':
        """从字典创建"""
        return cls(
            turbine_id=data.get('turbine_id', str(uuid.uuid4())[:8]),
            name=data.get('name', '风机'),
            model=data.get('model', '自定义'),
            tower_height_m=data.get('tower_height_m', 80.0),
            blade_length_m=data.get('blade_length_m', 50.0),
            blade_count=data.get('blade_count', 3),
            rotation_speed_rpm=data.get('rotation_speed_rpm', 15.0),
            tower_diameter_m=data.get('tower_diameter_m', 4.0),
            rcs_dbsm=data.get('rcs_dbsm', 40.0),
            material=data.get('material', '金属'),
            rated_power_mw=data.get('rated_power_mw', 2.0),
            latitude=data.get('latitude', 39.9142),
            longitude=data.get('longitude', 119.5974),
            altitude_m=data.get('altitude_m', 0.0),
            yaw_angle_deg=data.get('yaw_angle_deg', 0.0)
        )
