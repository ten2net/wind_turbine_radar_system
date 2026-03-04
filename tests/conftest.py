"""
单元测试配置
"""
import pytest
import sys
from pathlib import Path

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

@pytest.fixture
def sample_radar_config():
    """示例雷达配置"""
    from models import RadarConfig
    return RadarConfig(
        name="测试雷达",
        frequency_ghz=9.4,  # 9.4GHz (X波段)
        power_kw=100.0,  # 100kW
        antenna_gain_dbi=35.0,  # 35dBi
        beamwidth_deg=2.0,  # 2度
        beam_direction_deg=90.0,  # 90度
        pulse_width_us=1.0,  # 1微秒
        prf_hz=1000,  # 1000Hz
        latitude=39.9042,
        longitude=119.5774,
        altitude_m=100.0,
        max_range_km=100.0
    )

@pytest.fixture
def sample_turbine():
    """示例风机配置"""
    from models import Turbine
    return Turbine(
        name="测试风机",
        model="6MW海上风机",
        hub_height=120.0,
        rotor_diameter=150.0,
        latitude=39.9142,
        longitude=119.5874,
        altitude_m=10.0
    )

@pytest.fixture
def sample_scene():
    """示例场景"""
    from models import Scene
    scene = Scene()
    scene.radar.latitude = 39.9042
    scene.radar.longitude = 119.5774
    scene.radar.altitude_m = 100.0
    return scene
