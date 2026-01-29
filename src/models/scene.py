"""
场景配置模型
"""
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
import uuid
import json

from .radar import RadarConfig
from .turbine import Turbine
from .target import TargetConfig


@dataclass
class EnvironmentConfig:
    """环境配置类"""
    temperature_c: float = 15.0           # 温度(°C)
    humidity_percent: float = 60.0        # 湿度(%)
    pressure_hpa: float = 1013.0          # 气压(hPa)
    terrain_type: str = "平原"             # 地形类型
    wind_speed_ms: float = 10.0           # 风速(m/s)
    wind_direction_deg: float = 0.0       # 风向(度)
    
    def to_dict(self) -> dict:
        return {
            'temperature_c': self.temperature_c,
            'humidity_percent': self.humidity_percent,
            'pressure_hpa': self.pressure_hpa,
            'terrain_type': self.terrain_type,
            'wind_speed_ms': self.wind_speed_ms,
            'wind_direction_deg': self.wind_direction_deg
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'EnvironmentConfig':
        return cls(
            temperature_c=data.get('temperature_c', 15.0),
            humidity_percent=data.get('humidity_percent', 60.0),
            pressure_hpa=data.get('pressure_hpa', 1013.0),
            terrain_type=data.get('terrain_type', '平原'),
            wind_speed_ms=data.get('wind_speed_ms', 10.0),
            wind_direction_deg=data.get('wind_direction_deg', 0.0)
        )


@dataclass
class Scene:
    """场景配置类"""
    
    # 场景信息
    name: str = "新场景"
    description: str = ""
    
    # 组件配置
    radar: RadarConfig = field(default_factory=RadarConfig)
    turbines: List[Turbine] = field(default_factory=list)
    target: TargetConfig = field(default_factory=TargetConfig)
    environment: EnvironmentConfig = field(default_factory=EnvironmentConfig)
    
    # 系统信息
    scene_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    modified_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def add_turbine(self, turbine: Turbine) -> None:
        """添加风机"""
        self.turbines.append(turbine)
        self._update_modified_time()
    
    def remove_turbine(self, turbine_id: str) -> bool:
        """移除风机"""
        for i, t in enumerate(self.turbines):
            if t.turbine_id == turbine_id:
                self.turbines.pop(i)
                self._update_modified_time()
                return True
        return False
    
    def update_radar(self, radar: RadarConfig) -> None:
        """更新雷达配置"""
        self.radar = radar
        self._update_modified_time()
    
    def update_target(self, target: TargetConfig) -> None:
        """更新目标配置"""
        self.target = target
        self._update_modified_time()
    
    def clear_turbines(self) -> None:
        """清空所有风机"""
        self.turbines = []
        self._update_modified_time()
    
    def get_turbine_count(self) -> int:
        """获取风机数量"""
        return len(self.turbines)
    
    def _update_modified_time(self) -> None:
        """更新修改时间"""
        self.modified_at = datetime.now().isoformat()
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'scene_id': self.scene_id,
            'name': self.name,
            'description': self.description,
            'radar': self.radar.to_dict(),
            'turbines': [t.to_dict() for t in self.turbines],
            'target': self.target.to_dict(),
            'environment': self.environment.to_dict(),
            'created_at': self.created_at,
            'modified_at': self.modified_at
        }
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Scene':
        """从字典创建"""
        scene = cls(
            scene_id=data.get('scene_id', str(uuid.uuid4())[:8]),
            name=data.get('name', '新场景'),
            description=data.get('description', ''),
            created_at=data.get('created_at', datetime.now().isoformat()),
            modified_at=data.get('modified_at', datetime.now().isoformat())
        )
        
        # 加载雷达配置
        if 'radar' in data:
            scene.radar = RadarConfig.from_dict(data['radar'])
        
        # 加载风机列表
        if 'turbines' in data:
            scene.turbines = [Turbine.from_dict(t) for t in data['turbines']]
        
        # 加载目标配置
        if 'target' in data:
            scene.target = TargetConfig.from_dict(data['target'])
        
        # 加载环境配置
        if 'environment' in data:
            scene.environment = EnvironmentConfig.from_dict(data['environment'])
        
        return scene
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Scene':
        """从JSON字符串创建"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def save_to_file(self, filepath: str) -> None:
        """保存到文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.to_json())
    
    @classmethod
    def load_from_file(cls, filepath: str) -> 'Scene':
        """从文件加载"""
        with open(filepath, 'r', encoding='utf-8') as f:
            return cls.from_json(f.read())
