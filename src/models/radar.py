"""
雷达配置模型
"""
from dataclasses import dataclass, field
from typing import Optional
import uuid


@dataclass
class RadarConfig:
    """雷达配置类"""
    
    # 基本参数
    name: str = "雷达站"
    frequency_ghz: float = 3.0          # 工作频率(GHz)
    power_kw: float = 100.0             # 发射功率(kW)
    antenna_gain_dbi: float = 35.0      # 天线增益(dBi)
    beamwidth_deg: float = 1.5          # 波束宽度(度)
    pulse_width_us: float = 1.0         # 脉冲宽度(μs)
    prf_hz: float = 1000.0              # 脉冲重复频率(Hz)
    antenna_height_m: float = 50.0      # 天线高度(m)
    max_range_km: float = 100.0         # 最大探测距离(km)
    range_resolution_m: float = 150.0   # 距离分辨率(m)
    angle_resolution_deg: float = 1.0   # 角度分辨率(度)
    
    # 位置参数
    latitude: float = 39.9042           # 纬度
    longitude: float = 116.4074         # 经度
    altitude_m: float = 0.0             # 海拔高度(m)
    
    # 系统标识
    radar_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    
    def __post_init__(self):
        """参数验证"""
        # 确保参数在有效范围内
        self.frequency_ghz = max(0.1, min(100.0, self.frequency_ghz))
        self.power_kw = max(1.0, min(1000.0, self.power_kw))
        self.antenna_gain_dbi = max(0.0, min(60.0, self.antenna_gain_dbi))
        self.beamwidth_deg = max(0.1, min(10.0, self.beamwidth_deg))
        self.max_range_km = max(10.0, min(500.0, self.max_range_km))
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'radar_id': self.radar_id,
            'name': self.name,
            'frequency_ghz': self.frequency_ghz,
            'power_kw': self.power_kw,
            'antenna_gain_dbi': self.antenna_gain_dbi,
            'beamwidth_deg': self.beamwidth_deg,
            'pulse_width_us': self.pulse_width_us,
            'prf_hz': self.prf_hz,
            'antenna_height_m': self.antenna_height_m,
            'max_range_km': self.max_range_km,
            'range_resolution_m': self.range_resolution_m,
            'angle_resolution_deg': self.angle_resolution_deg,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'altitude_m': self.altitude_m
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'RadarConfig':
        """从字典创建"""
        return cls(
            radar_id=data.get('radar_id', str(uuid.uuid4())[:8]),
            name=data.get('name', '雷达站'),
            frequency_ghz=data.get('frequency_ghz', 3.0),
            power_kw=data.get('power_kw', 100.0),
            antenna_gain_dbi=data.get('antenna_gain_dbi', 35.0),
            beamwidth_deg=data.get('beamwidth_deg', 1.5),
            pulse_width_us=data.get('pulse_width_us', 1.0),
            prf_hz=data.get('prf_hz', 1000.0),
            antenna_height_m=data.get('antenna_height_m', 50.0),
            max_range_km=data.get('max_range_km', 100.0),
            range_resolution_m=data.get('range_resolution_m', 150.0),
            angle_resolution_deg=data.get('angle_resolution_deg', 1.0),
            latitude=data.get('latitude', 39.9042),
            longitude=data.get('longitude', 116.4074),
            altitude_m=data.get('altitude_m', 0.0)
        )
    
    def get_wavelength(self) -> float:
        """获取波长(m)"""
        c = 299792458  # 光速
        return c / (self.frequency_ghz * 1e9)
    
    def get_band(self) -> str:
        """获取雷达波段"""
        freq = self.frequency_ghz
        if freq < 0.3:
            return "HF"
        elif freq < 1.0:
            return "VHF/UHF"
        elif freq < 2.0:
            return "L"
        elif freq < 4.0:
            return "S"
        elif freq < 8.0:
            return "C"
        elif freq < 12.0:
            return "X"
        elif freq < 18.0:
            return "Ku"
        elif freq < 27.0:
            return "K"
        elif freq < 40.0:
            return "Ka"
        else:
            return "毫米波"
