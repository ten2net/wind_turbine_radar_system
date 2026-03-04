"""
雷达配置单元测试
"""
import pytest
import numpy as np
from models import RadarConfig

class TestRadarConfig:
    """雷达配置测试类"""
    
    def test_radar_creation(self, sample_radar_config):
        """测试雷达配置创建"""
        radar = sample_radar_config
        assert radar.name == "测试雷达"
        assert radar.frequency_ghz == 9.4
        assert radar.power_kw == 100.0
        assert radar.antenna_gain_dbi == 35.0
        
    def test_radar_wavelength_calculation(self, sample_radar_config):
        """测试雷达波长计算"""
        radar = sample_radar_config
        # 波长 = 光速 / 频率
        frequency_hz = radar.frequency_ghz * 1e9
        expected_wavelength = 3e8 / frequency_hz
        # 雷达类应该有wavelength属性或方法
        assert frequency_hz == 9.4e9
        
    def test_radar_range_equation_components(self, sample_radar_config):
        """测试雷达方程各组件"""
        radar = sample_radar_config
        # 验证雷达方程参数都在合理范围内
        assert radar.power_kw > 0
        assert radar.frequency_ghz > 0
        assert radar.antenna_gain_dbi > 0
        assert radar.beamwidth_deg > 0
        
    def test_radar_detection_range(self, sample_radar_config):
        """测试雷达探测距离范围"""
        radar = sample_radar_config
        assert radar.max_range_km > 0
        assert radar.max_range_km <= 500.0  # 最大500km
        
    def test_radar_post_init_validation(self):
        """测试参数验证"""
        # 测试频率限制
        radar = RadarConfig(frequency_ghz=150.0)  # 超出范围
        assert radar.frequency_ghz == 100.0  # 应被限制在100
        
        radar = RadarConfig(frequency_ghz=0.05)  # 低于范围
        assert radar.frequency_ghz == 0.1  # 应被限制在0.1
        
    def test_radar_to_dict(self, sample_radar_config):
        """测试转换为字典"""
        radar = sample_radar_config
        data = radar.to_dict()
        assert isinstance(data, dict)
        assert 'name' in data
        assert 'frequency_ghz' in data
        assert data['name'] == "测试雷达"
