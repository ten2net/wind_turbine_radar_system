"""
风机-雷达干扰评估系统 - 主应用
"""
from turtle import width
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pydeck
import time
from datetime import datetime

# 设置页面配置
st.set_page_config(
    page_title="风机-雷达干扰评估系统",
    page_icon="🌪️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 导入自定义模块
from models import RadarConfig, Turbine, TargetConfig, Scene
from models.turbine import TURBINE_MODELS
from models.target import TARGET_TYPES
from engine import EvalEngine
from engine.circular_motion_sim import CircularMotionSimulator, CircularMotionConfig
from utils.geo_utils import calculate_distance, calculate_bearing, calculate_destination

# 初始化session state
if 'scene' not in st.session_state:
    st.session_state.scene = Scene()
if 'evaluation_result' not in st.session_state:
    st.session_state.evaluation_result = None
if 'map_center' not in st.session_state:
    st.session_state.map_center = [39.9042, 120.4074]

# 初始化偏移量状态（用于连续添加风机）
if 'lat_offset_slider' not in st.session_state:
    st.session_state.lat_offset_slider = 0.0  # 纬度偏移滑块值
if 'lon_offset_slider' not in st.session_state:
    st.session_state.lon_offset_slider = 5.0  # 经度偏移滑块值（与滑块默认值一致）
if 'tian_count' not in st.session_state:
    st.session_state.tian_count = 0  # 当前田字形中的风机计数（0-3）
if 'tian_base_lat_offset' not in st.session_state:
    st.session_state.tian_base_lat_offset = 0.0  # 田字形基准纬度偏移
if 'tian_base_lon_offset' not in st.session_state:
    st.session_state.tian_base_lon_offset = 1.0  # 田字形基准经度偏移
if 'pending_lat_offset' not in st.session_state:
    st.session_state.pending_lat_offset = None  # 待处理的纬度偏移更新
if 'pending_lon_offset' not in st.session_state:
    st.session_state.pending_lon_offset = None  # 待处理的经度偏移更新

# 初始化圆周运动仿真状态
if 'circular_sim' not in st.session_state:
    st.session_state.circular_sim = None
if 'circular_sim_running' not in st.session_state:
    st.session_state.circular_sim_running = False
if 'circular_sim_config' not in st.session_state:
    st.session_state.circular_sim_config = None

# 自定义CSS样式
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .risk-low {
        color: #28a745;
        font-weight: bold;
    }
    .risk-medium {
        color: #ffc107;
        font-weight: bold;
    }
    .risk-high {
        color: #fd7e14;
        font-weight: bold;
    }
    .risk-critical {
        color: #dc3545;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)


def render_header():
    """渲染页面标题"""
    st.markdown('<p class="main-header">🌪️ 风机-雷达干扰评估系统</p>', 
                unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Wind Turbine - Radar Interference Assessment System</p>', 
                unsafe_allow_html=True)


def render_radar_config():
    """渲染雷达参数配置"""
    st.subheader("📡 雷达参数配置")
    
    radar = st.session_state.scene.radar
    
    with st.expander("基本参数", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            radar.name = st.text_input("雷达名称", value=radar.name)
            radar.frequency_ghz = st.number_input(
                "工作频率 (GHz)",
                min_value=0.1, max_value=100.0, value=radar.frequency_ghz, step=0.1
            )
            radar.power_kw = st.number_input(
                "发射功率 (kW)",
                min_value=1.0, max_value=1000.0, value=radar.power_kw, step=10.0
            )
            radar.antenna_gain_dbi = st.number_input(
                "天线增益 (dBi)",
                min_value=0.0, max_value=60.0, value=radar.antenna_gain_dbi, step=1.0
            )
        
        with col2:
            radar.beamwidth_deg = st.number_input(
                "波束宽度 (度)",
                min_value=0.1, max_value=10.0, value=radar.beamwidth_deg, step=0.1
            )
            radar.beam_direction_deg = st.number_input(
                "波束方向 (度，0=正北)",
                min_value=0.0, max_value=360.0, value=radar.beam_direction_deg, step=1.0
            )
            radar.antenna_height_m = st.number_input(
                "天线高度 (m)",
                min_value=0.0, max_value=500.0, value=radar.antenna_height_m, step=5.0
            )
            radar.max_range_km = st.number_input(
                "最大探测距离 (km)",
                min_value=10.0, max_value=500.0, value=radar.max_range_km, step=10.0
            )
            radar.prf_hz = st.number_input(
                "脉冲重复频率 (Hz)",
                min_value=100.0, max_value=10000.0, value=radar.prf_hz, step=100.0
            )
    
    with st.expander("位置信息"):
        col1, col2 = st.columns(2)
        with col1:
            radar.latitude = st.number_input(
                "纬度", value=radar.latitude, format="%.6f"
            )
        with col2:
            radar.longitude = st.number_input(
                "经度", value=radar.longitude, format="%.6f"
            )
        radar.altitude_m = st.number_input("海拔高度 (m)", value=radar.altitude_m)
    
    # 显示雷达波段
    band = radar.get_band()
    st.info(f"📊 雷达波段: **{band}** | 波长: **{radar.get_wavelength()*100:.2f} cm**")


def render_turbine_config():
    """渲染风机参数配置"""
    # 处理pending偏移量更新（必须在滑块渲染之前）
    if st.session_state.pending_lat_offset is not None and st.session_state.pending_lon_offset is not None:
        st.session_state.lat_offset_slider = st.session_state.pending_lat_offset
        st.session_state.lon_offset_slider = st.session_state.pending_lon_offset
        # 清除pending值
        st.session_state.pending_lat_offset = None
        st.session_state.pending_lon_offset = None
    
    st.subheader("🌪️ 风机参数配置")
    
    # 预设型号选择
    models = list(TURBINE_MODELS.keys())
    selected_model = st.selectbox("选择风机型号", models)
    
    # 获取预设参数
    defaults = TURBINE_MODELS[selected_model]
    
    with st.expander("详细参数", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            turbine_name = st.text_input("风机名称", value=f"风机{len(st.session_state.scene.turbines)+1}")
            tower_height = st.number_input(
                "塔筒高度 (m)",
                min_value=20.0, max_value=200.0,
                value=defaults["tower_height_m"], step=5.0
            )
            blade_length = st.number_input(
                "叶片长度 (m)",
                min_value=10.0, max_value=120.0,
                value=defaults["blade_length_m"], step=5.0
            )
            rotation_speed = st.number_input(
                "旋转速度 (rpm)",
                min_value=5.0, max_value=30.0,
                value=defaults["rotation_speed_rpm"], step=1.0
            )
        
        with col2:
            rcs = st.number_input(
                "RCS (dBm²)",
                min_value=10.0, max_value=60.0,
                value=defaults["rcs_dbsm"], step=1.0
            )
            blade_count = st.number_input(
                "叶片数量",
                min_value=2, max_value=5,
                value=defaults["blade_count"], step=1
            )
            tower_diameter = st.number_input(
                "塔筒直径 (m)",
                min_value=2.0, max_value=10.0,
                value=defaults["tower_diameter_m"], step=0.5
            )
    
    with st.expander("位置信息"):
        col1, col2 = st.columns(2)
        with col1:
            lat_offset = st.slider("纬度偏移 (km)", -50.0, 50.0, st.session_state.lat_offset_slider, 0.1, key="lat_offset_slider")
        with col2:
            lon_offset = st.slider("经度偏移 (km)", -100.0, 100.0, st.session_state.lon_offset_slider, 0.1, key="lon_offset_slider")
        
        # 计算实际坐标（简化：1度≈111km）
        radar = st.session_state.scene.radar
        turbine_lat = radar.latitude + lat_offset / 111
        turbine_lon = radar.longitude + lon_offset / (111 * np.cos(np.radians(radar.latitude)))
        
        # 计算风机到雷达的距离
        distance_m = calculate_distance(radar.latitude, radar.longitude, turbine_lat, turbine_lon)
        distance_km = distance_m / 1000
        
        st.info(f"📍 风机位置: 纬度 {turbine_lat:.6f}, 经度 {turbine_lon:.6f} | 距离雷达: {distance_km:.2f} km")
    
    # 添加风机按钮
    if st.button("➕ 添加风机", type="primary"):
        new_turbine = Turbine(
            name=turbine_name,
            model=selected_model,
            tower_height_m=tower_height,
            blade_length_m=blade_length,
            rotation_speed_rpm=rotation_speed,
            rcs_dbsm=rcs,
            blade_count=int(blade_count),
            tower_diameter_m=tower_diameter,
            latitude=turbine_lat,
            longitude=turbine_lon
        )
        st.session_state.scene.add_turbine(new_turbine)
        st.success(f"✅ 已添加风机: {turbine_name}")
        
        # 更新偏移量以实现连续添加和田字形布局
        # 获取当前滑块值（添加风机前的位置）
        current_lat_offset = lat_offset
        current_lon_offset = lon_offset
        
        # 如果是田字形的第一个风机，设置基准偏移量
        if st.session_state.tian_count == 0:
            st.session_state.tian_base_lat_offset = current_lat_offset
            st.session_state.tian_base_lon_offset = current_lon_offset
        
        # 增加田字形计数
        st.session_state.tian_count += 1
        
        # 计算新的偏移量：每个风机后都增加0.5km
        new_lat_offset = current_lat_offset + 0.5
        new_lon_offset = current_lon_offset + 0.5
        
        # 如果完成一个田字形（4个风机），向东平移2km，纬度重置
        if st.session_state.tian_count == 4:
            new_lon_offset = st.session_state.tian_base_lon_offset + 2.0  # 向东平移2km
            new_lat_offset = st.session_state.tian_base_lat_offset  # 纬度重置到基准
            st.session_state.tian_base_lon_offset = new_lon_offset  # 更新基准经度偏移，以便下一个田字形继续向东平移
            st.session_state.tian_count = 0  # 重置计数
        
        # 将新的偏移量存储到pending变量中，下次渲染时更新滑块
        # 确保偏移量在滑块范围内
        new_lat_offset = max(-50.0, min(50.0, new_lat_offset))
        new_lon_offset = max(-100.0, min(100.0, new_lon_offset))
        st.session_state.pending_lat_offset = new_lat_offset
        st.session_state.pending_lon_offset = new_lon_offset


def render_target_config():
    """渲染目标参数配置"""
    st.subheader("✈️ 目标参数配置")
    
    target = st.session_state.scene.target
    
    # 预设类型选择
    types = list(TARGET_TYPES.keys())
    selected_type = st.selectbox("选择目标类型", types, 
                                  index=types.index(target.target_type) if target.target_type in types else 0)
    
    # 获取预设参数
    type_defaults = TARGET_TYPES[selected_type]
    
    with st.expander("详细参数", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            target.target_type = selected_type
            target.rcs_dbsm = st.number_input(
                "目标RCS (dBm²)",
                min_value=-30.0, max_value=50.0,
                value=type_defaults["rcs_dbsm"], step=1.0
            )
            target.velocity_ms = st.number_input(
                "飞行速度 (m/s)",
                min_value=0.0, max_value=1000.0,
                value=type_defaults["velocity_ms"], step=10.0
            )
        
        with col2:
            target.altitude_m = st.number_input(
                "飞行高度 (m)",
                min_value=0.0, max_value=30000.0,
                value=type_defaults["altitude_m"], step=100.0
            )
            target.heading_deg = st.number_input(
                "航向角 (度)",
                min_value=0.0, max_value=360.0,
                value=0.0, step=5.0
            )
    
    with st.expander("位置信息"):
        col1, col2 = st.columns(2)
        with col1:
            target.latitude = st.number_input(
                "目标纬度", value=target.latitude, format="%.6f"
            )
        with col2:
            target.longitude = st.number_input(
                "目标经度", value=target.longitude, format="%.6f"
            )
        
        # 计算并显示目标与雷达的距离和方位
        radar = st.session_state.scene.radar
        distance_m = calculate_distance(radar.latitude, radar.longitude, target.latitude, target.longitude)
        distance_km = distance_m / 1000
        bearing = calculate_bearing(radar.latitude, radar.longitude, target.latitude, target.longitude)
        
        st.info(f"📍 目标距离: **{distance_km:.2f} km** | 方位角: **{bearing:.1f}°**")


def render_turbine_list():
    """渲染风机列表"""
    st.subheader("📋 已添加风机")
    
    turbines = st.session_state.scene.turbines
    
    if not turbines:
        st.info("暂无风机，请从左侧栏中添加")
        return
    
    # 创建风机数据表格
    turbine_data = []
    for t in turbines:
        distance = calculate_distance(
            st.session_state.scene.radar.latitude,
            st.session_state.scene.radar.longitude,
            t.latitude, t.longitude
        )
        turbine_data.append({
            'ID': t.turbine_id,
            '名称': t.name,
            '型号': t.model,
            '塔高(m)': t.tower_height_m,
            '叶片(m)': t.blade_length_m,
            '转速(rpm)': t.rotation_speed_rpm,
            'RCS(dBm²)': t.rcs_dbsm,
            '距离(km)': round(distance / 1000, 2)
        })
    
    df = pd.DataFrame(turbine_data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # 删除风机
    if st.button("🗑️ 清空所有风机"):
        st.session_state.scene.clear_turbines()
        st.success("✅ 已清空所有风机")
        st.experimental_rerun()

def get_icon_data(icon: str) -> dict:
    """获取图标数据"""
    return {
        "url": f"https://cdn.jsdelivr.net/npm/@mapbox/maki@6.2.0/icons/{icon}-15.svg",
        "id": icon,
        "width": 242,
        "height": 242,
        "anchorY": 242,
        "mask": True  # Set to True to allow custom coloring
    }


def calculate_turbine_impact_zones(radar, turbines, max_range_km):
    """
    计算风机对雷达覆盖的影响区域
    
    Args:
        radar: 雷达配置对象
        turbines: 风机列表
        max_range_km: 最大探测距离（km）
        
    Returns:
        impact_zones: 影响区域多边形数据列表
    """
    impact_zones = []
    max_range_m = max_range_km * 1000
    
    for turbine in turbines:
        # 计算雷达到风机的方位角
        bearing = calculate_bearing(radar.latitude, radar.longitude, 
                                   turbine.latitude, turbine.longitude)
        
        # 计算距离
        distance = calculate_distance(radar.latitude, radar.longitude,
                                     turbine.latitude, turbine.longitude)
        
        # 根据波束宽度确定扇形区域宽度
        sector_width = radar.beamwidth_deg
        
        # 基于遮挡模型计算影响因子
        # 简化的影响模型：影响强度随距离和角度衰减
        distance_factor = min(1.0, max(0.1, 1.0 - distance / max_range_m))
        
        # 计算方位角差（归一化到0-180度）
        angle_diff = abs(bearing - radar.beam_direction_deg)
        angle_diff = min(angle_diff, 360 - angle_diff)
        
        # 基于高斯天线方向图的衰减因子
        angular_attenuation = np.exp(-2.776 * (angle_diff / sector_width)**2)
        
        # 综合影响因子
        impact_factor = distance_factor * angular_attenuation
        
        # 计算影响区域的边界点
        # 影响区域是从风机位置向外扩散的扇形，表示遮挡影响的范围
        polygon_points = []
        
        # 添加雷达中心点
        polygon_points.append([radar.longitude, radar.latitude])
        
        # 计算扇形左边界
        left_bearing = (bearing - sector_width / 2) % 360.0
        
        # 沿着左边界从雷达向外延伸到最大范围
        for r in np.linspace(distance * 0.2, max_range_m, 5):
            dest_lat, dest_lon = calculate_destination(
                radar.latitude, radar.longitude, left_bearing, r
            )
            polygon_points.append([dest_lon, dest_lat])
        
        # 沿着最大范围弧线从左到右
        for b in np.linspace(left_bearing, (bearing + sector_width / 2) % 360.0, 10):
            dest_lat, dest_lon = calculate_destination(
                radar.latitude, radar.longitude, b, max_range_m
            )
            polygon_points.append([dest_lon, dest_lat])
        
        # 沿着右边界从最大范围回到雷达
        right_bearing = (bearing + sector_width / 2) % 360.0
        for r in np.linspace(max_range_m, distance * 0.2, 5):
            dest_lat, dest_lon = calculate_destination(
                radar.latitude, radar.longitude, right_bearing, r
            )
            polygon_points.append([dest_lon, dest_lat])
        
        # 闭合多边形
        polygon_points.append([radar.longitude, radar.latitude])
        
        # 根据影响因子确定颜色（橙色到红色渐变）
        # 影响因子越大，颜色越红（越严重）
        red = int(255 * impact_factor)
        green = int(200 * (1.0 - impact_factor * 0.5))
        blue = int(100 * (1.0 - impact_factor))
        alpha = int(150 * impact_factor + 50)  # 50-200透明度
        
        impact_zones.append({
            'polygon': polygon_points,
            'color': [red, green, blue, alpha],
            'name': turbine.name,
            'type': f'影响区域 (强度: {impact_factor:.2f})',
            'turbine_name': turbine.name,  # 保留原始字段
            'impact_factor': round(impact_factor, 2),
            'distance_km': round(distance / 1000, 2)
        })
    
    return impact_zones


def calculate_combined_blocked_polygon(radar, turbines, max_range_km):
    """
    计算所有风机合并的遮挡区域多边形（风机后面的扇形子区域）
    
    Args:
        radar: 雷达配置对象
        turbines: 风机列表
        max_range_km: 最大探测距离（km）
        
    Returns:
        polygon_points: 合并遮挡区域的多边形点列表 [[lon, lat], ...]
    """
    if not turbines:
        return []
    
    # 计算雷达的扇形参数
    beam_center = radar.beam_direction_deg
    beam_width = radar.beamwidth_deg
    max_range_m = max_range_km * 1000
    
    # 获取每个风机的位置
    turbine_points = []
    for turbine in turbines:
        # 计算风机的方位角和距离
        bearing = calculate_bearing(radar.latitude, radar.longitude, turbine.latitude, turbine.longitude)
        distance = calculate_distance(radar.latitude, radar.longitude, turbine.latitude, turbine.longitude)
        
        # 检查风机是否在雷达的扇形覆盖范围内
        angle_diff = abs(bearing - beam_center)
        angle_diff = min(angle_diff, 360 - angle_diff)
        
        if angle_diff <= beam_width / 2:
            # 风机在扇形范围内，计算其后面的遮挡区域
            turbine_points.append({
                'lon': turbine.longitude,
                'lat': turbine.latitude,
                'bearing': bearing,
                'distance': distance
            })
    
    if not turbine_points:
        return []
    
    # 按方位角排序
    turbine_points.sort(key=lambda p: p['bearing'])
    
    # 构建遮挡区域多边形（风机后面的扇形子区域）
    blocked_polygon = []
    
    # 计算每个风机的遮挡扇区并合并
    # 遮挡区域是从风机位置向外延伸的扇形子区域
    
    # 简化的遮挡模型：为每个风机创建一个小的扇形遮挡区域
    for turbine in turbine_points:
        # 风机的方位角
        turbine_bearing = turbine['bearing']
        turbine_distance = turbine['distance']
        
        # 计算遮挡扇区的左右边界（基于波束宽度的一小部分）
        # 遮挡扇区的宽度与风机距离成反比（距离越远，遮挡角度越小）
        shadow_width = min(5.0, beam_width * 0.3)  # 最大5度的遮挡扇区
        
        left_bearing = (turbine_bearing - shadow_width / 2) % 360.0
        right_bearing = (turbine_bearing + shadow_width / 2) % 360.0
        
        # 添加风机位置作为遮挡区域的起点
        blocked_polygon.append([turbine['lon'], turbine['lat']])
        
        # 沿着遮挡扇区的左边界向外延伸到最大距离
        step = max(1.0, shadow_width / 10.0)
        
        if right_bearing >= left_bearing:
            # 不跨越0度
            bearing = left_bearing
            while bearing <= right_bearing:
                dest_lat, dest_lon = calculate_destination(
                    radar.latitude, radar.longitude, bearing, max_range_m
                )
                blocked_polygon.append([dest_lon, dest_lat])
                bearing += step
        else:
            # 跨越0度
            bearing = left_bearing
            while bearing <= 360.0:
                dest_lat, dest_lon = calculate_destination(
                    radar.latitude, radar.longitude, bearing, max_range_m
                )
                blocked_polygon.append([dest_lon, dest_lat])
                bearing += step
            
            bearing = 0.0
            while bearing <= right_bearing:
                dest_lat, dest_lon = calculate_destination(
                    radar.latitude, radar.longitude, bearing, max_range_m
                )
                blocked_polygon.append([dest_lon, dest_lat])
                bearing += step
    
    # 闭合多边形（回到第一个风机位置）
    if blocked_polygon:
        blocked_polygon.append(blocked_polygon[0])
    
    return blocked_polygon


def render_map():
    """渲染地图视图"""
    st.subheader("🗺️ 场景地图")
    
    # 覆盖范围显示控制
    if 'show_coverage' not in st.session_state:
        st.session_state.show_coverage = True
    show_coverage = st.checkbox("显示雷达覆盖范围", value=st.session_state.show_coverage, key="show_coverage_checkbox")
    st.session_state.show_coverage = show_coverage
    
    radar = st.session_state.scene.radar
    turbines = st.session_state.scene.turbines
    target = st.session_state.scene.target
    
    # 创建地图数据
    map_data = []
    map_data.append({
        'lat': radar.latitude,
        'lon': radar.longitude,
        'name': radar.name,
        'type': '雷达站',
        'size': 20,
        'color': [255, 0, 0],
        'icon': get_icon_data('communications-tower')
    })
    
    # 添加风机
    for t in turbines:
        map_data.append({
            'lat': t.latitude,
            'lon': t.longitude,
            'name': t.name,
            'type': f'风机 ({t.model})',
            'size': 20,
            'color': [255, 255, 255],
            'icon': get_icon_data('windmill')
        })
    
    # 添加目标
    map_data.append({
        'lat': target.latitude,
        'lon': target.longitude,
        'name': f"目标 ({target.target_type})",
        'type': f"目标 - RCS: {target.rcs_dbsm} dBm² | 高度: {target.altitude_m}m",
        'size': 15,
        'color': [0, 150, 255],
        'icon': get_icon_data('airport')
    })
    
    df = pd.DataFrame(map_data)
    
    # Mapbox API密钥
    MAPBOX_API_KEY = "***REMOVED***"
    
    # 准备图层数据
    if len(df) > 0:
        # 创建图标图层
        icon_layer = pydeck.Layer(
            'IconLayer',
            data=df,
            get_icon='icon',
            get_size='size',
            get_color="color",
            size_scale=2,
            get_position=['lon', 'lat'],
            pickable=True,
            opacity=1.0
        )
        
        # 创建雷达覆盖范围多边形图层（如果雷达有最大探测距离且用户选择显示）
        coverage_layers = []
        if radar.max_range_km > 0 and st.session_state.show_coverage:
            # 将最大探测距离转换为米
            max_range_m = radar.max_range_km * 1000
            # 获取波束参数
            beam_center = radar.beam_direction_deg
            beam_width = radar.beamwidth_deg
            
            # 计算整个扇形区域（绿色可见区域）
            full_sector_points = []
            
            # 如果波束宽度大于等于360度，显示完整圆形
            if beam_width >= 360.0:
                for bearing in range(0, 361, 10):  # 包括360度以闭合多边形
                    dest_lat, dest_lon = calculate_destination(
                        radar.latitude, radar.longitude, bearing, max_range_m
                    )
                    full_sector_points.append([dest_lon, dest_lat])
            else:
                # 计算左右边界方位角（归一化到0-360度）
                left_bearing = (beam_center - beam_width / 2) % 360.0
                right_bearing = (beam_center + beam_width / 2) % 360.0
                
                # 添加雷达中心点作为顶点
                full_sector_points.append([radar.longitude, radar.latitude])
                
                # 添加左侧边界点
                dest_lat, dest_lon = calculate_destination(
                    radar.latitude, radar.longitude, left_bearing, max_range_m
                )
                full_sector_points.append([dest_lon, dest_lat])
                
                # 添加弧线上的点（从左侧到右侧）
                # 计算步长，确保至少2个点，最多36个点
                step = max(1.0, beam_width / 20.0)
                
                if right_bearing >= left_bearing:
                    # 不跨越0度
                    bearing = left_bearing
                    while bearing <= right_bearing:
                        dest_lat, dest_lon = calculate_destination(
                            radar.latitude, radar.longitude, bearing, max_range_m
                        )
                        full_sector_points.append([dest_lon, dest_lat])
                        bearing += step
                    # 确保最后一个点正好是右边界
                    if full_sector_points[-1] != [dest_lon, dest_lat]:
                        dest_lat, dest_lon = calculate_destination(
                            radar.latitude, radar.longitude, right_bearing, max_range_m
                        )
                        full_sector_points.append([dest_lon, dest_lat])
                else:
                    # 跨越0度，从左边界到360度，再从0度到右边界
                    bearing = left_bearing
                    while bearing <= 360.0:
                        dest_lat, dest_lon = calculate_destination(
                            radar.latitude, radar.longitude, bearing, max_range_m
                        )
                        full_sector_points.append([dest_lon, dest_lat])
                        bearing += step
                    # 从0度开始
                    bearing = 0.0
                    while bearing <= right_bearing:
                        dest_lat, dest_lon = calculate_destination(
                            radar.latitude, radar.longitude, bearing, max_range_m
                        )
                        full_sector_points.append([dest_lon, dest_lat])
                        bearing += step
                    # 确保最后一个点正好是右边界
                    if full_sector_points[-1] != [dest_lon, dest_lat]:
                        dest_lat, dest_lon = calculate_destination(
                            radar.latitude, radar.longitude, right_bearing, max_range_m
                        )
                        full_sector_points.append([dest_lon, dest_lat])
                
                # 闭合多边形（回到雷达中心点）
                full_sector_points.append([radar.longitude, radar.latitude])
            
            # 创建整个扇形区域的绿色图层（可见区域）
            full_sector_data = [{
                'polygon': full_sector_points,
                'color': [0, 255, 0, 100]  # 半透明绿色 (RGBA)
            }]
            
            full_sector_layer = pydeck.Layer(
                'PolygonLayer',
                data=full_sector_data,
                get_polygon='polygon',
                get_fill_color='color',
                get_line_color=[0, 255, 0],
                get_line_width=2,
                filled=True,
                stroked=True,
                pickable=False,
                opacity=0.6
            )
            coverage_layers.append(full_sector_layer)
            
            # 计算合并的遮挡区域（红色区域）
            if turbines:
                blocked_polygon = calculate_combined_blocked_polygon(radar, turbines, radar.max_range_km)
                if blocked_polygon:
                    blocked_data = [{
                        'polygon': blocked_polygon,
                        'color': [255, 100, 100, 120]  # 统一浅红色 (RGBA)
                    }]
                    
                    blocked_layer = pydeck.Layer(
                        'PolygonLayer',
                        data=blocked_data,
                        get_polygon='polygon',
                        get_fill_color='color',
                        get_line_color=[255, 100, 100],
                        get_line_width=1,
                        filled=True,
                        stroked=False,
                        pickable=True,
                        opacity=0.6
                    )
                    coverage_layers.append(blocked_layer)
        
        # 设置视图状态（以雷达位置为中心）
        zoom_level = 10 if not turbines else 9  # 有风机时缩小一些
        view_state = pydeck.ViewState(
            latitude=radar.latitude,
            longitude=radar.longitude,
            zoom=zoom_level,
            pitch=0,
            bearing=0
        )
        
        # 创建地图（合并图标图层和覆盖范围图层），确保点图层在最上层
        all_layers = coverage_layers + [icon_layer]
        r = pydeck.Deck(
            layers=all_layers,
            initial_view_state=view_state,
            map_style='mapbox://styles/mapbox/streets-zh-v1',
            api_keys={"mapbox": MAPBOX_API_KEY},
            tooltip={
                'html': '<b>{name}</b><br/>{type}',
                'style': {
                    'backgroundColor': 'steelblue',
                    'color': 'white'
                }
            }
        )
        
        # 渲染地图
        st.pydeck_chart(r, use_container_width=True)
        
        # 显示颜色图例
        if radar.max_range_km > 0 and st.session_state.show_coverage:
            st.markdown("""
            **颜色图例**：
            - 🟢 绿色区域：雷达可见区域（无遮挡）
            - 🔴 红色区域：被风机遮挡区域（不可见）
            """)
    else:
        st.info("暂无数据，请先配置雷达和风机")
    
    # 显示统计信息
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("雷达位置", f"{radar.latitude:.4f}, {radar.longitude:.4f}")
    with col2:
        st.metric("风机数量", len(turbines))
    with col3:
        if turbines:
            distances = [
                calculate_distance(radar.latitude, radar.longitude, t.latitude, t.longitude)
                for t in turbines
            ]
            st.metric("平均距离", f"{np.mean(distances)/1000:.2f} km")


def render_evaluation_button():
    """渲染评估按钮"""
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        if st.button("🔍 开始评估", type="primary", use_container_width=True):
            if not st.session_state.scene.turbines:
                st.warning("⚠️ 请先添加至少一台风机")
                return
            
            with st.spinner("正在执行评估计算..."):
                engine = EvalEngine()
                result = engine.evaluate(st.session_state.scene)
                st.session_state.evaluation_result = result
            
            st.success("✅ 评估完成！")


def render_blocking_results(result):
    """渲染遮挡分析结果"""
    blocking = result.blocking
    
    # 指标卡片
    col1, col2, col3 = st.columns(3)
    
    with col1:
        risk_class = get_risk_class(blocking.get_risk_level())
        st.metric(
            label="遮挡因子",
            value=f"{blocking.blocking_factor:.1f}%",
            delta=blocking.get_risk_level()
        )
    
    with col2:
        st.metric(
            label="遮挡持续时间",
            value=f"{blocking.blocking_duration:.1f}%"
        )
    
    with col3:
        st.metric(
            label="受影响风机数",
            value=len(blocking.affected_sectors)
        )
    
    # 时域遮挡图
    if blocking.time_series:
        fig = go.Figure()
        radial_range = [0, 100]  # 默认范围
        fig.add_trace(go.Scatter(
            x=list(range(len(blocking.time_series))),
            y=blocking.time_series,
            mode='lines',
            name='遮挡比例',
            line=dict(color='red', width=2),
            fill='tozeroy'
        ))
        fig.update_layout(
            title="一个旋转周期内的遮挡变化",
            xaxis_title="时间采样点",
            yaxis_title="遮挡比例 (%)",
            height=300
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # 受影响扇区表格
    if blocking.affected_sectors:
        st.subheader("受影响扇区详情")
        # 创建展平的数据
        flat_data = []
        for sector in blocking.affected_sectors:
            flat = {
                '风机ID': sector['turbine_id'],
                '风机名称': sector['turbine_name'],
                '遮挡因子(%)': sector['blocking'],
                '遮挡持续时间(%)': sector['duration'],
                '扇区中心角(°)': sector['sector']['center'],
                '扇区起始角(°)': sector['sector']['start'],
                '扇区终止角(°)': sector['sector']['end'],
                '扇区宽度(°)': sector['sector']['width'],
                '距离(km)': sector['distance_km']
            }
            flat_data.append(flat)
        sector_df = pd.DataFrame(flat_data)
        st.dataframe(sector_df, use_container_width=True)


def render_scattering_results(result):
    """渲染散射分析结果"""
    scattering = result.scattering
    
    # 指标卡片
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="干扰功率",
            value=f"{scattering.interference_power:.1f} dBm"
        )
    
    with col2:
        st.metric(
            label="目标回波功率",
            value=f"{scattering.target_power:.1f} dBm"
        )
    
    with col3:
        delta_text = f"恶化 {scattering.sjr_degradation:.1f} dB" if scattering.sjr_degradation > 0 else "正常"
        st.metric(
            label="信干比",
            value=f"{scattering.sjr:.1f} dB",
            delta=delta_text
        )
    
    # 距离剖面图
    if scattering.range_profile:
        fig = go.Figure()
        radial_range = [0, 100]  # 默认范围
        fig.add_trace(go.Scatter(
            x=list(range(len(scattering.range_profile))),
            y=scattering.range_profile,
            mode='lines',
            name='干扰功率',
            line=dict(color='orange', width=2)
        ))
        fig.update_layout(
            title="距离剖面干扰分布",
            xaxis_title="距离单元",
            yaxis_title="干扰功率 (dBm)",
            height=300
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # 各风机干扰详情
    if scattering.affected_turbines:
        st.subheader("各风机干扰详情")
        # 重命名列名
        rename_map = {
            'turbine_id': '风机ID',
            'turbine_name': '风机名称',
            'distance_km': '距离(km)',
            'rcs_dbsm': 'RCS(dBm²)',
            'power_dbm': '干扰功率(dBm)'
        }
        turbine_df = pd.DataFrame(scattering.affected_turbines)
        turbine_df = turbine_df.rename(columns=rename_map)
        st.dataframe(turbine_df, use_container_width=True)


def render_doppler_results(result):
    """渲染多普勒分析结果"""
    doppler = result.doppler
    
    # 指标卡片
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="最大多普勒频移",
            value=f"{doppler.max_doppler_shift:.0f} Hz"
        )
    
    with col2:
        st.metric(
            label="多普勒带宽",
            value=f"{doppler.doppler_bandwidth:.0f} Hz"
        )
    
    with col3:
        st.metric(
            label="速度展宽",
            value=f"{doppler.velocity_spread:.1f} m/s"
        )
    
    # 受影响的滤波器
    st.info(f"🎯 受影响的滤波器: {', '.join(doppler.affected_filters)}")
    
    # 多普勒频谱图
    if doppler.spectrum_data:
        fig = go.Figure()
        radial_range = [0, 100]  # 默认范围
        fig.add_trace(go.Scatter(
            x=doppler.spectrum_data['frequencies'],
            y=doppler.spectrum_data['amplitude'],
            mode='lines',
            fill='tozeroy',
            name='频谱',
            line=dict(color='purple', width=2)
        ))
        fig.update_layout(
            title="多普勒频谱特征",
            xaxis_title="频率 (Hz)",
            yaxis_title="归一化幅度",
            height=300
        )
        st.plotly_chart(fig, use_container_width=True)


def create_gauge_chart(title, value, threshold, unit, color):
    """创建仪表盘图表"""
    # 计算百分比（0-100%）
    percentage = min(100, max(0, (1 - value / threshold) * 100)) if threshold > 0 else 0
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=percentage,
        number={'suffix': '%', 'font': {'size': 24}},
        title={'text': title, 'font': {'size': 16}},
        delta={'reference': 100, 'relative': False, 'valueformat': '.1f', 'suffix': '%'},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "darkblue"},
            'bar': {'color': color, 'thickness': 0.75},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [0, 30], 'color': '#ffcccc'},  # 红色区域 - 差
                {'range': [30, 70], 'color': '#ffffcc'}, # 黄色区域 - 中
                {'range': [70, 100], 'color': '#ccffcc'} # 绿色区域 - 好
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 70
            }
        }
    ))
    
    fig.update_layout(
        height=300,
        margin=dict(l=20, r=20, t=50, b=20),
        paper_bgcolor="white",
        font={'size': 12}
    )
    
    return fig, percentage


def render_accuracy_results(result):
    """渲染精度分析结果 - 单独分析每个精度指标"""
    accuracy = result.accuracy
    
    # 归一化阈值定义（基于典型雷达性能）
    angle_threshold = 2.0    # 度 - 测角误差阈值
    range_threshold = 50.0   # 米 - 测距误差阈值
    velocity_threshold = 5.0 # 米/秒 - 测速误差阈值
    
    st.subheader("📊 精度指标单独分析")
    
    # 创建三个独立的仪表盘
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**🎯 测角精度**")
        angle_fig, angle_pct = create_gauge_chart(
            f"误差: {accuracy.angle_error:.3f}°",
            accuracy.angle_error,
            angle_threshold,
            "°",
            "#1f77b4"
        )
        st.plotly_chart(angle_fig, use_container_width=True)
        st.caption(f"阈值: {angle_threshold}° | 降级: {accuracy.angle_degradation:.1f}%")
    
    with col2:
        st.markdown("**📏 测距精度**")
        range_fig, range_pct = create_gauge_chart(
            f"误差: {accuracy.range_error:.0f}m",
            accuracy.range_error,
            range_threshold,
            "m",
            "#ff7f0e"
        )
        st.plotly_chart(range_fig, use_container_width=True)
        st.caption(f"阈值: {range_threshold}m | 降级: {accuracy.range_degradation:.1f}%")
    
    with col3:
        st.markdown("**🚀 测速精度**")
        velocity_fig, velocity_pct = create_gauge_chart(
            f"误差: {accuracy.velocity_error:.1f}m/s",
            accuracy.velocity_error,
            velocity_threshold,
            "m/s",
            "#2ca02c"
        )
        st.plotly_chart(velocity_fig, use_container_width=True)
        st.caption(f"阈值: {velocity_threshold}m/s | 降级: {accuracy.velocity_degradation:.1f}%")
    
    # 综合精度评估
    st.markdown("---")
    st.subheader("📈 综合精度评估")
    
    # 计算综合得分
    overall_score = (angle_pct + range_pct + velocity_pct) / 3
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.metric(
            label="综合精度得分",
            value=f"{overall_score:.1f}%",
            delta=f"降级 {accuracy.overall_degradation:.1f}%"
        )
    with col2:
        # 综合进度条
        st.progress(overall_score / 100, text=f"综合性能: {overall_score:.1f}%")
    
    # 详细数据表格
    with st.expander("📋 查看详细数据", expanded=False):
        data = {
            '指标': ['测角精度', '测距精度', '测速精度', '综合精度'],
            '实际误差': [
                f"{accuracy.angle_error:.3f}°",
                f"{accuracy.range_error:.0f}m",
                f"{accuracy.velocity_error:.1f}m/s",
                "-"
            ],
            '阈值': [f"{angle_threshold}°", f"{range_threshold}m", f"{velocity_threshold}m/s", "-"],
            '性能得分': [f"{angle_pct:.1f}%", f"{range_pct:.1f}%", f"{velocity_pct:.1f}%", f"{overall_score:.1f}%"],
            '降级比例': [
                f"{accuracy.angle_degradation:.1f}%",
                f"{accuracy.range_degradation:.1f}%",
                f"{accuracy.velocity_degradation:.1f}%",
                f"{accuracy.overall_degradation:.1f}%"
            ]
        }
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    
    # 评估建议
    st.markdown("---")
    st.subheader("💡 精度评估建议")
    
    recommendations = []
    if angle_pct < 70:
        recommendations.append(f"🎯 **测角精度不足**: 当前误差 {accuracy.angle_error:.3f}° 超过阈值 {angle_threshold}° 的30%，建议检查雷达天线对准或增加信号处理算法优化。")
    if range_pct < 70:
        recommendations.append(f"📏 **测距精度不足**: 当前误差 {accuracy.range_error:.0f}m 超过阈值 {range_threshold}m 的30%，建议优化脉冲压缩算法或提高信噪比。")
    if velocity_pct < 70:
        recommendations.append(f"🚀 **测速精度不足**: 当前误差 {accuracy.velocity_error:.1f}m/s 超过阈值 {velocity_threshold}m/s 的30%，建议增加相干积累时间或优化多普勒滤波器。")
    
    if not recommendations:
        st.success("✅ 所有精度指标均在可接受范围内，系统性能良好！")
    else:
        for rec in recommendations:
            st.warning(rec)
    
    # 显示精度评分说明
    with st.expander("📊 精度评分说明", expanded=False):
        st.markdown("""
        **精度评分机制：**
        
        每个精度指标使用仪表盘形式展示，评分范围0-100%：
        - **绿色区域 (70-100%)**: 性能良好，满足要求
        - **黄色区域 (30-70%)**: 性能一般，需要关注
        - **红色区域 (0-30%)**: 性能较差，需要优化
        
        **评分计算方式：**
        - 得分 = 100 × (1 - 实际误差 / 阈值)
        - 误差越小，得分越高
        - 误差超过阈值时，得分可能为负（显示为0%）
        
        **阈值设置（基于典型雷达性能）：
        - 测角误差阈值：≤ 2.0° 为可接受
        - 测距误差阈值：≤ 50m 为可接受  
        - 测速误差阈值：≤ 5.0m/s 为可接受
        
        **实际应用建议**：
        - 得分 ≥ 70%：性能良好，无需调整
        - 得分 30-70%：性能一般，建议监控
        - 得分 < 30%：性能较差，强烈建议优化系统配置
        """)


def render_multipath_results(result):
    """渲染多径效应分析结果"""
    multipath = result.multipath
    
    # 指标卡片
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="峰谷比",
            value=f"{multipath.peak_to_null_ratio:.1f} dB",
            delta=f"衰落深度 {multipath.fading_depth:.1f} dB"
        )
    
    with col2:
        st.metric(
            label="多径距离差",
            value=f"{multipath.multipath_distance:.1f} m",
            delta=f"时延扩展 {multipath.delay_spread:.1f} ns"
        )
    
    with col3:
        if multipath.constructive_count > multipath.destructive_count:
            delta_text = f"同相叠加 {multipath.constructive_count} 次"
        else:
            delta_text = f"反相抵消 {multipath.destructive_count} 次"
        st.metric(
            label="相位偏移",
            value=f"{multipath.phase_shift_deg:.1f}°",
            delta=delta_text
        )
    
    # 多径效应统计
    st.info(f"🌊 多径效应统计: 同相叠加 {multipath.constructive_count} 次 | 反相抵消 {multipath.destructive_count} 次 | 方向图畸变 {multipath.pattern_distortion:.1f}°")
    
    # 多径衰落频率显示
    st.subheader("多径衰落特性")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("衰落频率", f"{multipath.fading_frequency:.2f} Hz")
    with col2:
        st.metric("相位变化", f"{multipath.phase_shift_deg:.1f}°")
    
    # 多径影响雷达图
    categories = ['峰谷比', '衰落深度', '相位偏移', '方向图畸变']
    values = [
        max(0, 60 - multipath.peak_to_null_ratio) / 60 * 100,  # 峰谷比越小越好
        max(0, 40 - multipath.fading_depth) / 40 * 100,         # 衰落深度越小越好
        max(0, 180 - abs(multipath.phase_shift_deg - 180)) / 180 * 100,  # 相位偏移接近180度最好
        max(0, 30 - multipath.pattern_distortion) / 30 * 100    # 方向图畸变越小越好
    ]
    
    fig = go.Figure(data=go.Scatterpolar(
        r=values + [values[0]],
        theta=categories + [categories[0]],
        fill='toself',
        name='多径影响指标',
        line_color='blue',
        fillcolor='rgba(0, 0, 255, 0.2)'
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=False,
        title="多径效应影响评估",
        height=350
    )
    st.plotly_chart(fig, use_container_width=True)


def render_diffraction_results(result):
    """渲染绕射损耗分析结果"""
    diffraction = result.diffraction
    
    # 指标卡片
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="刃形绕射损耗",
            value=f"{diffraction.knife_edge_loss:.1f} dB",
            delta=f"菲涅尔余隙 {diffraction.fresnel_zone_clearance:.1f} m"
        )
    
    with col2:
        st.metric(
            label="主瓣畸变",
            value=f"{diffraction.main_lobe_distortion:.1f} dB",
            delta=f"副瓣增强 {diffraction.side_lobe_enhancement:.1f} dB"
        )
    
    with col3:
        st.metric(
            label="有效增益损失",
            value=f"{diffraction.effective_gain_loss:.1f} dB",
            delta=f"不对称度 {diffraction.pattern_asymmetry:.1f}"
        )
    
    # 绕射遮挡比显示
    st.info(f"🗻 绕射遮挡比: {diffraction.blockage_ratio:.2f} | 方向图不对称度: {diffraction.pattern_asymmetry:.1f}")
    
    # 绕射影响分析
    st.subheader("绕射影响详情")
    
    if diffraction.terrain_shadowing:
        # 显示地形遮蔽数据
        terrain_df = pd.DataFrame([
            {
                '风机名称': item['turbine_name'],
                '距离 (m)': round(item['distance'], 1),
                '障碍物高度 (m)': round(item['obstacle_height'], 1),
                '菲涅尔区半径 (m)': round(item['fresnel_zone_radius'], 1),
                '余隙 (m)': round(item['fresnel_clearance'], 1),
                '绕射损耗 (dB)': round(item['knife_edge_loss'], 1),
                '遮挡比': round(item['blockage_ratio'], 2)
            }
            for item in diffraction.terrain_shadowing
        ])
        st.dataframe(terrain_df, use_container_width=True)
    
    # 绕射损耗与距离关系图（简化）
    st.subheader("绕射损耗趋势")
    
    # 生成模拟数据
    distances = np.linspace(1000, 10000, 10)  # 1-10km
    simulated_losses = 20 * np.log10(distances / 1000) + np.random.normal(0, 2, len(distances))
    
    fig = go.Figure()
    radial_range = [0, 100]  # 默认范围
    fig.add_trace(go.Scatter(
        x=distances,
        y=simulated_losses,
        mode='lines+markers',
        name='绕射损耗趋势',
        line=dict(color='orange', width=2),
        marker=dict(size=8, color='red')
    ))
    
    # 添加当前点
    if diffraction.terrain_shadowing:
        avg_distance = np.mean([item['distance'] for item in diffraction.terrain_shadowing])
        fig.add_trace(go.Scatter(
            x=[avg_distance],
            y=[diffraction.knife_edge_loss],
            mode='markers',
            name='当前配置',
            marker=dict(size=12, color='green', symbol='star')
        ))
    
    fig.update_layout(
        title="绕射损耗随距离变化趋势",
        xaxis_title="距离 (m)",
        yaxis_title="绕射损耗 (dB)",
        height=300
    )
    st.plotly_chart(fig, use_container_width=True)


def render_results():
    """渲染评估结果"""
    result = st.session_state.evaluation_result
    
    if result is None:
        return
    
    st.markdown("---")
    st.header("📊 评估结果")
    
    # 综合风险等级
    overall_risk = result.get_overall_risk()
    risk_score = result.get_risk_score()
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("综合评估")
        risk_class = get_risk_class(overall_risk)
        st.markdown(f"<h3>风险等级: <span class='{risk_class}'>{overall_risk}</span></h3>", 
                   unsafe_allow_html=True)
    with col2:
        st.subheader("风险评分")
        st.progress(risk_score / 100, text=f"{risk_score:.1f}/100")
    
    # 建议
    recommendations = result.get_recommendations()
    if recommendations:
        st.subheader("💡 评估建议")
        for rec in recommendations:
            st.info(rec)
    
    # 详细结果标签页
    tabs = st.tabs(["🚫 遮挡分析", "📡 散射分析", "🌊 多普勒分析", "🎯 精度分析", "🌊 多径效应", "🗻 绕射损耗"])
    
    with tabs[0]:
        render_blocking_results(result)
    
    with tabs[1]:
        render_scattering_results(result)
    
    with tabs[2]:
        render_doppler_results(result)
    
    with tabs[3]:
        render_accuracy_results(result)
    
    with tabs[4]:
        render_multipath_results(result)
    
    with tabs[5]:
        render_diffraction_results(result)


def get_risk_class(risk_level: str) -> str:
    """获取风险等级对应的CSS类"""
    risk_map = {
        "低风险": "risk-low",
        "中等风险": "risk-medium",
        "高风险": "risk-high",
        "极高风险": "risk-critical"
    }
    return risk_map.get(risk_level, "risk-low")


def render_circular_motion_sim():
    """渲染圆周运动仿真页面"""
    st.markdown("---")
    st.header("🔄 风电场目标圆周运动仿真")
    st.markdown("目标以风电场中心为圆心，在1km和5km半径的圆周上运动，实时显示雷达探测性能变化")
    
    radar = st.session_state.scene.radar
    turbines = st.session_state.scene.turbines
    
    if not turbines:
        st.warning("⚠️ 请先添加至少一台风机作为风电场中心参考")
        return
    
    # 计算风电场中心（所有风机的平均位置）
    center_lat = np.mean([t.latitude for t in turbines])
    center_lon = np.mean([t.longitude for t in turbines])
    
    # 仿真配置
    with st.expander("⚙️ 仿真配置", expanded=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            velocity_ms = st.number_input(
                "目标速度 (m/s)",
                min_value=10.0, max_value=500.0,
                value=100.0, step=10.0
            )
            altitude_m = st.number_input(
                "飞行高度 (m)",
                min_value=100.0, max_value=20000.0,
                value=1000.0, step=100.0
            )
        
        with col2:
            rcs_dbsm = st.number_input(
                "目标RCS (dBm²)",
                min_value=-30.0, max_value=50.0,
                value=10.0, step=1.0
            )
            target_type = st.selectbox(
                "目标类型",
                list(TARGET_TYPES.keys()),
                index=0
            )
        
        with col3:
            radius_inner = st.number_input(
                "内圈半径 (km)",
                min_value=0.5, max_value=10.0,
                value=1.0, step=0.5
            )
            radius_outer = st.number_input(
                "外圈半径 (km)",
                min_value=1.0, max_value=20.0,
                value=5.0, step=0.5
            )
    
    # 显示风电场中心位置
    st.info(f"📍 风电场中心: 纬度 {center_lat:.6f}, 经度 {center_lon:.6f}")
    
    # 控制按钮
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        if st.button("▶️ 开始仿真", type="primary", use_container_width=True):
            # 创建仿真配置
            config = CircularMotionConfig(
                center_lat=center_lat,
                center_lon=center_lon,
                radius_inner_km=radius_inner,
                radius_outer_km=radius_outer,
                velocity_ms=velocity_ms,
                altitude_m=altitude_m,
                rcs_dbsm=rcs_dbsm,
                target_type=target_type
            )
            
            # 创建仿真器
            st.session_state.circular_sim = CircularMotionSimulator(
                config=config,
                radar=radar,
                turbines=turbines
            )
            st.session_state.circular_sim.start()
            st.session_state.circular_sim_running = True
            st.session_state.circular_sim_config = config
            st.success("✅ 仿真已启动")
    
    with col2:
        if st.button("⏹️ 停止仿真", use_container_width=True):
            if st.session_state.circular_sim:
                st.session_state.circular_sim.stop()
            st.session_state.circular_sim_running = False
            st.info("⏹️ 仿真已停止")
    
    with col3:
        if st.button("🔄 重置仿真", use_container_width=True):
            if st.session_state.circular_sim:
                st.session_state.circular_sim.reset()
            st.session_state.circular_sim_running = False
            st.info("🔄 仿真已重置")
    
    # 实时仿真显示
    if st.session_state.circular_sim_running and st.session_state.circular_sim:
        # 创建占位符用于实时更新
        map_placeholder = st.empty()
        metrics_placeholder = st.empty()
        
        # 执行一次更新
        sim = st.session_state.circular_sim
        inner_state, outer_state = sim.update(500)  # 500ms更新一次
        
        if inner_state and outer_state:
            # 计算探测指标
            inner_metrics = sim.calculate_detection_metrics(inner_state)
            outer_metrics = sim.calculate_detection_metrics(outer_state)
            
            # 获取当前位置
            inner_pos, outer_pos = sim.get_current_positions()
            
            # 渲染地图
            with map_placeholder.container():
                render_circular_motion_map(sim, inner_pos, outer_pos, center_lat, center_lon)
            
            # 渲染指标
            with metrics_placeholder.container():
                render_circular_motion_metrics(inner_pos, outer_pos, inner_metrics, outer_metrics)
            
            # 自动刷新
            time.sleep(0.5)
            st.experimental_rerun()
    else:
        # 显示静态说明
        st.info("👆 点击'开始仿真'按钮启动圆周运动仿真")


def render_circular_motion_map(sim, inner_pos, outer_pos, center_lat, center_lon):
    """渲染圆周运动地图"""
    st.subheader("📍 实时位置追踪")
    
    radar = st.session_state.scene.radar
    turbines = st.session_state.scene.turbines
    
    # 创建地图数据
    map_data = []
    
    # 添加雷达
    map_data.append({
        'lat': radar.latitude,
        'lon': radar.longitude,
        'name': radar.name,
        'type': '雷达站',
        'size': 20,
        'color': [255, 0, 0],
        'icon': get_icon_data('communications-tower')
    })
    
    # 添加风机
    for t in turbines:
        map_data.append({
            'lat': t.latitude,
            'lon': t.longitude,
            'name': t.name,
            'type': f'风机 ({t.model})',
            'size': 15,
            'color': [255, 255, 255],
            'icon': get_icon_data('windmill')
        })
    
    # 添加风电场中心
    map_data.append({
        'lat': center_lat,
        'lon': center_lon,
        'name': '风电场中心',
        'type': '圆心',
        'size': 15,
        'color': [128, 128, 128],
        'icon': get_icon_data('circle')
    })
    
    # 添加目标
    if inner_pos:
        map_data.append({
            'lat': inner_pos['lat'],
            'lon': inner_pos['lon'],
            'name': inner_pos['label'],
            'type': f"内圈目标 | 探测概率: {inner_pos['detection_probability']*100:.1f}% | SNR: {inner_pos['snr_db']:.1f}dB",
            'size': 18,
            'color': [0, 255, 255] if not inner_pos['is_blocked'] else [255, 0, 0],
            'icon': get_icon_data('airport')
        })
    
    if outer_pos:
        map_data.append({
            'lat': outer_pos['lat'],
            'lon': outer_pos['lon'],
            'name': outer_pos['label'],
            'type': f"外圈目标 | 探测概率: {outer_pos['detection_probability']*100:.1f}% | SNR: {outer_pos['snr_db']:.1f}dB",
            'size': 18,
            'color': [255, 165, 0] if not outer_pos['is_blocked'] else [255, 0, 0],
            'icon': get_icon_data('airport')
        })
    
    df = pd.DataFrame(map_data)
    
    # Mapbox API密钥
    MAPBOX_API_KEY = "***REMOVED***"
    
    # 创建图层
    icon_layer = pydeck.Layer(
        'IconLayer',
        data=df,
        get_icon='icon',
        get_size='size',
        get_color="color",
        size_scale=2,
        get_position=['lon', 'lat'],
        pickable=True,
        opacity=1.0
    )
    
    # 添加圆周轨迹
    trajectory_layers = []
    
    # 获取轨迹数据
    inner_traj, outer_traj = sim.get_trajectory_data()
    
    # 内圈轨迹
    if inner_traj:
        inner_path = [[p['lon'], p['lat']] for p in inner_traj]
        inner_path_data = [{'path': inner_path, 'color': [0, 255, 255, 150]}]
        
        inner_path_layer = pydeck.Layer(
            'PathLayer',
            data=inner_path_data,
            get_path='path',
            get_color='color',
            get_width=3,
            width_scale=1,
            width_min_pixels=2,
            pickable=False
        )
        trajectory_layers.append(inner_path_layer)
    
    # 外圈轨迹
    if outer_traj:
        outer_path = [[p['lon'], p['lat']] for p in outer_traj]
        outer_path_data = [{'path': outer_path, 'color': [255, 165, 0, 150]}]
        
        outer_path_layer = pydeck.Layer(
            'PathLayer',
            data=outer_path_data,
            get_path='path',
            get_color='color',
            get_width=3,
            width_scale=1,
            width_min_pixels=2,
            pickable=False
        )
        trajectory_layers.append(outer_path_layer)
    
    # 设置视图
    view_state = pydeck.ViewState(
        latitude=center_lat,
        longitude=center_lon,
        zoom=11,
        pitch=0,
        bearing=0
    )
    
    # 创建地图
    r = pydeck.Deck(
        layers=trajectory_layers + [icon_layer],
        initial_view_state=view_state,
        map_style='mapbox://styles/mapbox/streets-zh-v1',
        api_keys={"mapbox": MAPBOX_API_KEY},
        tooltip={
            'html': '<b>{name}</b><br/>{type}',
            'style': {
                'backgroundColor': 'steelblue',
                'color': 'white'
            }
        }
    )
    
    st.pydeck_chart(r, use_container_width=True)


def render_circular_motion_metrics(inner_pos, outer_pos, inner_metrics, outer_metrics):
    """渲染圆周运动指标"""
    st.subheader("📊 实时探测指标")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**🔵 内圈目标 (1km)**")
        if inner_pos:
            metric_col1, metric_col2, metric_col3 = st.columns(3)
            
            with metric_col1:
                st.metric(
                    "探测概率",
                    f"{inner_pos['detection_probability']*100:.1f}%",
                    delta="被遮挡" if inner_pos['is_blocked'] else "正常",
                    delta_color="inverse" if inner_pos['is_blocked'] else "normal"
                )
            
            with metric_col2:
                st.metric(
                    "信噪比",
                    f"{inner_pos['snr_db']:.1f} dB"
                )
            
            with metric_col3:
                st.metric(
                    "雷达到目标",
                    f"{inner_pos['distance_to_radar_km']:.2f} km"
                )
            
            if inner_pos['is_blocked'] and inner_pos['blocked_by']:
                st.warning(f"⚠️ 被以下风机遮挡: {', '.join(inner_pos['blocked_by'])}")
        else:
            st.info("等待数据...")
    
    with col2:
        st.markdown("**🟠 外圈目标 (5km)**")
        if outer_pos:
            metric_col1, metric_col2, metric_col3 = st.columns(3)
            
            with metric_col1:
                st.metric(
                    "探测概率",
                    f"{outer_pos['detection_probability']*100:.1f}%",
                    delta="被遮挡" if outer_pos['is_blocked'] else "正常",
                    delta_color="inverse" if outer_pos['is_blocked'] else "normal"
                )
            
            with metric_col2:
                st.metric(
                    "信噪比",
                    f"{outer_pos['snr_db']:.1f} dB"
                )
            
            with metric_col3:
                st.metric(
                    "雷达到目标",
                    f"{outer_pos['distance_to_radar_km']:.2f} km"
                )
            
            if outer_pos['is_blocked'] and outer_pos['blocked_by']:
                st.warning(f"⚠️ 被以下风机遮挡: {', '.join(outer_pos['blocked_by'])}")
        else:
            st.info("等待数据...")
    
    # 显示图例
    st.markdown("""
    **颜色说明：**
    - 🔵 青色：内圈目标（1km半径）正常
    - 🟠 橙色：外圈目标（5km半径）正常
    - 🔴 红色：目标被风机遮挡
    """)


def main():
    """主函数"""
    render_header()
    
    # 页面选择
    page = st.sidebar.radio(
        "选择功能模块",
        ["📊 干扰评估", "🔄 圆周运动仿真"],
        index=0
    )
    
    if page == "📊 干扰评估":
        # 干扰评估页面
        with st.sidebar:
            st.image("https://img.icons8.com/color/96/wind-turbine.png", width=80)
            
            render_radar_config()
            st.markdown("---")
            render_turbine_config()
            st.markdown("---")
            render_target_config()
        
        render_map()
        render_turbine_list()
        render_evaluation_button()
        render_results()
        
    else:
        # 圆周运动仿真页面
        with st.sidebar:
            st.image("https://img.icons8.com/color/96/wind-turbine.png", width=80)
            st.markdown("### 🔄 圆周运动仿真")
            st.markdown("目标以风电场中心为圆心做圆周运动")
            
            # 显示当前配置的风机和雷达信息
            st.markdown("---")
            st.markdown("**当前场景信息：**")
            st.markdown(f"- 风机数量: {len(st.session_state.scene.turbines)}")
            st.markdown(f"- 雷达: {st.session_state.scene.radar.name}")
            
            if st.session_state.scene.turbines:
                center_lat = np.mean([t.latitude for t in st.session_state.scene.turbines])
                center_lon = np.mean([t.longitude for t in st.session_state.scene.turbines])
                st.markdown(f"- 风电场中心: ({center_lat:.4f}, {center_lon:.4f})")
        
        render_circular_motion_sim()
    
    # 页脚
    st.markdown("---")
    st.markdown(
        "<p style='text-align: center; color: #666;'>"
        "© 2026 风机-雷达干扰评估系统 | Version 0.1 (MVP)</p>",
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
