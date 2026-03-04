"""
遮挡效应引擎单元测试
"""
import pytest
import numpy as np
from engine.blocking import BlockingEngine
from models import RadarConfig, Turbine, TargetConfig

class TestBlockingEngine:
    """遮挡效应引擎测试类"""
    
    def test_blocking_factor_calculation(self):
        """测试遮挡因子计算"""
        engine = BlockingEngine()
        
        # 测试完全遮挡情况
        blocking_factor = 1.0
        result = engine.calculate_attenuation(blocking_factor)
        assert result <= -20  # 衰减应大于20dB
        
        # 测试无遮挡情况
        blocking_factor = 0.0
        result = engine.calculate_attenuation(blocking_factor)
        assert result == 0  # 无衰减
        
    def test_blocking_detection(self, sample_radar_config, sample_turbine):
        """测试遮挡检测逻辑"""
        engine = BlockingEngine()
        
        # 设置雷达和风机位置（风机在雷达和目标之间）
        radar = sample_radar_config
        turbine = sample_turbine
        
        # 目标位置（在风机后方）
        target = TargetConfig(
            name="测试目标",
            target_type="飞机",
            rcs=10.0,
            latitude=39.9242,  # 更远
            longitude=120.4274,
            altitude=1000.0
        )
        
        # 检测是否被遮挡
        is_blocked = engine.is_target_blocked(radar, turbine, target)
        assert isinstance(is_blocked, bool)
        
    def test_blocking_geometry(self):
        """测试遮挡几何计算"""
        engine = BlockingEngine()
        
        # 测试投影计算
        turbine_width = 150.0  # 叶片长度
        distance = 10000.0  # 10km
        
        # 计算投影角度
        projection_angle = engine.calculate_projection_angle(turbine_width, distance)
        
        # 投影角度应在合理范围内
        assert projection_angle > 0
        assert projection_angle < 180  # 度
