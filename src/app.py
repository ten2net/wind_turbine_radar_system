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


def parse_turbine_csv(csv_file):
    """
    解析风机CSV文件
    
    CSV格式要求：
    - 必须列：name, latitude, longitude
    - 可选列：tower_height_m, blade_length_m, rotation_speed_rpm, rcs_dbsm, blade_count, tower_diameter_m, model
    
    Returns:
        list: 风机配置字典列表
    """
    try:
        df = pd.read_csv(csv_file)
        
        # 检查必需列
        required_cols = ['name', 'latitude', 'longitude']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            return None, f"CSV文件缺少必需列: {', '.join(missing_cols)}"
        
        turbines = []
        for idx, row in df.iterrows():
            # 获取型号，默认为第一个可用型号
            model = row.get('model', list(TURBINE_MODELS.keys())[0])
            if model not in TURBINE_MODELS:
                model = list(TURBINE_MODELS.keys())[0]
            defaults = TURBINE_MODELS[model]
            
            turbine = {
                'name': str(row['name']),
                'latitude': float(row['latitude']),
                'longitude': float(row['longitude']),
                'model': model,
                'tower_height_m': float(row.get('tower_height_m', defaults['tower_height_m'])),
                'blade_length_m': float(row.get('blade_length_m', defaults['blade_length_m'])),
                'rotation_speed_rpm': float(row.get('rotation_speed_rpm', defaults['rotation_speed_rpm'])),
                'rcs_dbsm': float(row.get('rcs_dbsm', defaults['rcs_dbsm'])),
                'blade_count': int(row.get('blade_count', defaults['blade_count'])),
                'tower_diameter_m': float(row.get('tower_diameter_m', defaults['tower_diameter_m']))
            }
            turbines.append(turbine)
        
        return turbines, None
    except Exception as e:
        return None, f"解析CSV文件失败: {str(e)}"


def render_turbine_csv_upload():
    """渲染风机CSV上传界面"""
    st.markdown("---")
    st.subheader("📁 批量上传风机坐标")
    
    with st.expander("CSV文件格式说明", expanded=False):
        st.markdown("""
        **CSV文件格式要求：**
        
        1. **必需列**（必须包含）：
           - `name`: 风机名称
           - `latitude`: 纬度（度）
           - `longitude`: 经度（度）
        
        2. **可选列**（如未提供则使用默认值）：
           - `model`: 风机型号（如V90-2.0MW、SG2.5-130等）
           - `tower_height_m`: 塔筒高度（米）
           - `blade_length_m`: 叶片长度（米）
           - `rotation_speed_rpm`: 旋转速度（rpm）
           - `rcs_dbsm`: RCS（dBm²）
           - `blade_count`: 叶片数量
           - `tower_diameter_m`: 塔筒直径（米）
        
        **示例CSV内容：**
        ```csv
        name,latitude,longitude,model,tower_height_m
        风机01,39.9042,120.4074,V90-2.0MW,80
        风机02,39.9142,120.4174,V90-2.0MW,80
        风机03,39.9242,120.4274,SG2.5-130,100
        ```
        
        **提示：** 您也可以先下载模板，填写后再上传。
        """)
        
        # 提供CSV模板下载
        template_df = pd.DataFrame([
            {
                'name': '风机01',
                'latitude': 39.9042,
                'longitude': 120.4074,
                'model': 'V90-2.0MW',
                'tower_height_m': 80,
                'blade_length_m': 45,
                'rotation_speed_rpm': 14,
                'rcs_dbsm': 30,
                'blade_count': 3,
                'tower_diameter_m': 3.5
            },
            {
                'name': '风机02',
                'latitude': 39.9142,
                'longitude': 120.4174,
                'model': 'V90-2.0MW',
                'tower_height_m': 80,
                'blade_length_m': 45,
                'rotation_speed_rpm': 14,
                'rcs_dbsm': 30,
                'blade_count': 3,
                'tower_diameter_m': 3.5
            }
        ])
        
        csv_template = template_df.to_csv(index=False)
        st.download_button(
            label="📥 下载CSV模板",
            data=csv_template,
            file_name='turbine_template.csv',
            mime='text/csv'
        )
    
    # 文件上传
    uploaded_file = st.file_uploader(
        "上传风机坐标CSV文件",
        type=['csv'],
        help="支持.csv格式文件"
    )
    
    if uploaded_file is not None:
        turbines, error = parse_turbine_csv(uploaded_file)
        
        if error:
            st.error(f"❌ {error}")
        else:
            st.success(f"✅ 成功解析 {len(turbines)} 个风机")
            
            # 显示预览
            with st.expander("📋 数据预览", expanded=True):
                preview_df = pd.DataFrame([
                    {
                        '名称': t['name'],
                        '纬度': t['latitude'],
                        '经度': t['longitude'],
                        '型号': t['model'],
                        '塔高(m)': t['tower_height_m']
                    }
                    for t in turbines
                ])
                st.dataframe(preview_df, use_container_width=True, hide_index=True)
            
            # 添加到场景按钮
            col1, col2 = st.columns(2)
            with col1:
                if st.button("➕ 添加到场景", type="primary", use_container_width=True):
                    added_count = 0
                    for turbine_data in turbines:
                        new_turbine = Turbine(
                            name=turbine_data['name'],
                            model=turbine_data['model'],
                            tower_height_m=turbine_data['tower_height_m'],
                            blade_length_m=turbine_data['blade_length_m'],
                            rotation_speed_rpm=turbine_data['rotation_speed_rpm'],
                            rcs_dbsm=turbine_data['rcs_dbsm'],
                            blade_count=turbine_data['blade_count'],
                            tower_diameter_m=turbine_data['tower_diameter_m'],
                            latitude=turbine_data['latitude'],
                            longitude=turbine_data['longitude']
                        )
                        st.session_state.scene.add_turbine(new_turbine)
                        added_count += 1
                    
                    st.success(f"✅ 已成功添加 {added_count} 个风机到场景")
                    st.experimental_rerun()
            
            with col2:
                if st.button("🗑️ 清空现有风机后添加", use_container_width=True):
                    st.session_state.scene.clear_turbines()
                    added_count = 0
                    for turbine_data in turbines:
                        new_turbine = Turbine(
                            name=turbine_data['name'],
                            model=turbine_data['model'],
                            tower_height_m=turbine_data['tower_height_m'],
                            blade_length_m=turbine_data['blade_length_m'],
                            rotation_speed_rpm=turbine_data['rotation_speed_rpm'],
                            rcs_dbsm=turbine_data['rcs_dbsm'],
                            blade_count=turbine_data['blade_count'],
                            tower_diameter_m=turbine_data['tower_diameter_m'],
                            latitude=turbine_data['latitude'],
                            longitude=turbine_data['longitude']
                        )
                        st.session_state.scene.add_turbine(new_turbine)
                        added_count += 1
                    
                    st.success(f"✅ 已清空现有风机并添加 {added_count} 个新风机")
                    st.experimental_rerun()


def render_turbine_manual_config():
    """渲染风机手动配置界面"""
    # 预设型号选择
    models = list(TURBINE_MODELS.keys())
    selected_model = st.selectbox("选择风机型号", models, key="manual_model")
    
    # 获取预设参数
    defaults = TURBINE_MODELS[selected_model]
    
    with st.expander("详细参数", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            turbine_name = st.text_input("风机名称", value=f"风机{len(st.session_state.scene.turbines)+1}", key="manual_name")
            tower_height = st.number_input(
                "塔筒高度 (m)",
                min_value=20.0, max_value=200.0,
                value=defaults["tower_height_m"], step=5.0,
                key="manual_tower_height"
            )
            blade_length = st.number_input(
                "叶片长度 (m)",
                min_value=10.0, max_value=120.0,
                value=defaults["blade_length_m"], step=5.0,
                key="manual_blade_length"
            )
            rotation_speed = st.number_input(
                "旋转速度 (rpm)",
                min_value=5.0, max_value=30.0,
                value=defaults["rotation_speed_rpm"], step=1.0,
                key="manual_rotation_speed"
            )
        
        with col2:
            rcs = st.number_input(
                "RCS (dBm²)",
                min_value=10.0, max_value=60.0,
                value=defaults["rcs_dbsm"], step=1.0,
                key="manual_rcs"
            )
            blade_count = st.number_input(
                "叶片数量",
                min_value=2, max_value=5,
                value=defaults["blade_count"], step=1,
                key="manual_blade_count"
            )
            tower_diameter = st.number_input(
                "塔筒直径 (m)",
                min_value=2.0, max_value=10.0,
                value=defaults["tower_diameter_m"], step=0.5,
                key="manual_tower_diameter"
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
    if st.button("➕ 添加风机", type="primary", key="manual_add_button"):
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
    
    # 选择配置方式
    config_mode = st.radio(
        "选择配置方式",
        ["手动添加", "CSV文件批量上传"],
        horizontal=True,
        help="手动添加：逐个配置风机位置；CSV上传：批量导入风机坐标"
    )
    
    if config_mode == "手动添加":
        render_turbine_manual_config()
    else:
        render_turbine_csv_upload()


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
                value=90.0, step=5.0
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
        'angle':0,
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
            'angle':0,
            'color': [255, 255, 255],
            'icon': get_icon_data('windmill')
        })
    
    # 添加目标（转换航向角为PyDeck旋转角度）
    # heading是正北顺时针，pydeck的angle是东逆时针，转换：angle = 90 - heading
    target_angle = (90 - target.heading_deg) % 360
    map_data.append({
        'lat': target.latitude,
        'lon': target.longitude,
        'name': f"目标 ({target.target_type})",
        'type': f"目标 - RCS: {target.rcs_dbsm} dBm² | 高度: {target.altitude_m}m | 航向: {target.heading_deg:.1f}°",
        'size': 15,
        'angle': target_angle,
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
            get_angle="angle",
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


def generate_micro_doppler_spectrogram(rotation_rpm, blade_length, num_blades=3, duration=2.0, prf=1000):
    """
    生成风机微多普勒时频图数据
    
    Args:
        rotation_rpm: 叶片转速 (rpm)
        blade_length: 叶片长度 (m)
        num_blades: 叶片数量
        duration: 仿真时长 (秒)
        prf: 脉冲重复频率 (Hz)
    
    Returns:
        dict: 包含时间和频率轴的频谱数据
    """
    # 计算基本参数
    rotation_freq = rotation_rpm / 60.0  # 旋转频率 (Hz)
    rotation_period = 1.0 / rotation_freq  # 旋转周期 (s)
    blade_tip_velocity = 2 * np.pi * blade_length * rotation_freq  # 叶尖线速度 (m/s)
    
    # 假设雷达波长为10cm (X波段)
    wavelength = 0.1
    
    # 计算最大微多普勒频移
    max_doppler = 2 * blade_tip_velocity / wavelength  # 最大频移 (Hz)
    
    # 时间轴
    time = np.linspace(0, duration, int(duration * prf))
    
    # 频率轴
    freq_resolution = 1 / duration
    freqs = np.linspace(-max_doppler * 1.2, max_doppler * 1.2, 256)
    
    # 生成微多普勒时频图数据
    spectrogram = np.zeros((len(freqs), len(time)))
    
    for blade_idx in range(num_blades):
        blade_phase_offset = blade_idx * (2 * np.pi / num_blades)  # 叶片间相位差
        
        for t_idx, t in enumerate(time):
            # 叶片旋转角度
            theta = 2 * np.pi * rotation_freq * t + blade_phase_offset
            
            # 叶片不同部位的速度分量 (径向)
            # 叶尖速度最大，叶根速度为0
            for r_ratio in [0.2, 0.5, 0.8, 1.0]:  # 沿叶片不同位置
                r = r_ratio * blade_length
                v_radial = 2 * np.pi * rotation_freq * r * np.cos(theta)  # 径向速度分量
                doppler_shift = 2 * v_radial / wavelength
                
                # 在时频图上添加能量
                freq_idx = np.argmin(np.abs(freqs - doppler_shift))
                if 0 <= freq_idx < len(freqs):
                    # 高斯窗函数模拟频谱展宽
                    amplitude = np.exp(-((freqs - doppler_shift) / (max_doppler * 0.05))**2)
                    amplitude *= (r_ratio ** 0.5)  # 叶尖RCS更强
                    spectrogram[:, t_idx] += amplitude
    
    # 添加塔筒回波 (零频附近)
    tower_doppler_width = 50  # 塔筒多普勒展宽
    tower_idx = np.argmin(np.abs(freqs - 0))
    for t_idx in range(len(time)):
        tower_spectrum = np.exp(-((freqs - 0) / tower_doppler_width)**2) * 0.3
        spectrogram[:, t_idx] += tower_spectrum
    
    # 归一化
    spectrogram = spectrogram / np.max(spectrogram)
    
    return {
        'time': time,
        'frequencies': freqs,
        'spectrogram': spectrogram,
        'rotation_period': rotation_period,
        'max_doppler': max_doppler,
        'blade_tip_velocity': blade_tip_velocity
    }


def render_doppler_results(result):
    """渲染多普勒分析结果"""
    doppler = result.doppler
    
    # ========== 第一部分：基础指标卡片 ==========
    st.subheader("📊 基础多普勒参数")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="最大多普勒频移",
            value=f"{doppler.max_doppler_shift:.0f} Hz",
            help="叶片叶尖产生的最大多普勒频移"
        )
    
    with col2:
        st.metric(
            label="多普勒带宽",
            value=f"{doppler.doppler_bandwidth:.0f} Hz",
            help="多普勒频谱的3dB带宽"
        )
    
    with col3:
        st.metric(
            label="速度展宽",
            value=f"{doppler.velocity_spread:.1f} m/s",
            help="由叶片旋转引起的径向速度展宽"
        )
    
    with col4:
        st.metric(
            label="MTI改善因子恶化",
            value=f"{doppler.mti_degradation:.1f} dB",
            help="风机杂波导致的MTI性能下降"
        )
    
    # 受影响的滤波器
    if doppler.affected_filters:
        st.info(f"🎯 受影响的滤波器: {', '.join(doppler.affected_filters)}")
    
    # ========== 第二部分：多普勒频谱与时频分析 ==========
    st.markdown("---")
    st.subheader("🔬 高级多普勒分析")
    
    # 创建子标签页
    doppler_tabs = st.tabs([
        "📈 多普勒频谱", 
        "⏱️ 微多普勒时频图", 
        "🎯 盲速与模糊分析",
        "🔧 MTI/MTD滤波器性能"
    ])
    
    # Tab 1: 多普勒频谱
    with doppler_tabs[0]:
        if doppler.spectrum_data:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=doppler.spectrum_data['frequencies'],
                    y=doppler.spectrum_data['amplitude'],
                    mode='lines',
                    fill='tozeroy',
                    name='频谱',
                    line=dict(color='purple', width=2)
                ))
                
                # 添加杂波谱宽标注
                clutter_width = getattr(doppler, 'clutter_spectrum_width', 0)
                if clutter_width > 0:
                    f_center = 0
                    f_width = clutter_width / 2
                    fig.add_vrect(
                        x0=-f_width, x1=f_width,
                        fillcolor="red", opacity=0.1,
                        layer="below", line_width=0,
                        annotation_text="杂波谱宽", annotation_position="top left"
                    )
                
                fig.update_layout(
                    title="多普勒频谱特征",
                    xaxis_title="频率 (Hz)",
                    yaxis_title="归一化幅度",
                    height=350
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.markdown("#### 📋 频谱参数")
                st.markdown(f"""
                - **谱中心**: 0 Hz
                - **谱宽度**: {doppler.doppler_bandwidth:.1f} Hz
                - **3dB带宽**: {getattr(doppler, 'clutter_spectrum_width', 0):.1f} Hz
                - **峰值幅度**: {np.max(doppler.spectrum_data['amplitude']):.2f}
                - **平均幅度**: {np.mean(doppler.spectrum_data['amplitude']):.2f}
                """)
                
                # 微多普勒特征说明
                st.markdown("#### 🔄 微多普勒特征")
                st.markdown(f"""
                - **叶尖速度**: {getattr(doppler, 'blade_tip_velocity', 0):.1f} m/s
                - **旋转频率**: {getattr(doppler, 'blade_rotation_freq', 0):.2f} Hz
                - **调制周期**: {getattr(doppler, 'modulation_period', 0):.3f} s
                """)
        else:
            st.info("暂无多普勒频谱数据")
    
    # Tab 2: 微多普勒时频图
    with doppler_tabs[1]:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # 使用默认参数生成微多普勒时频图
            if st.session_state.scene and st.session_state.scene.turbines:
                turbine = st.session_state.scene.turbines[0]  # 使用第一个风机
                micro_data = generate_micro_doppler_spectrogram(
                    rotation_rpm=turbine.rotation_speed_rpm,
                    blade_length=turbine.blade_length_m,
                    num_blades=turbine.blade_count,
                    duration=2.0,
                    prf=1000
                )
                num_blades_display = turbine.blade_count
            else:
                # 使用默认参数
                micro_data = generate_micro_doppler_spectrogram(
                    rotation_rpm=14.0,
                    blade_length=45.0,
                    num_blades=3,
                    duration=2.0,
                    prf=1000
                )
                num_blades_display = 3
            
            # 绘制时频图
            fig = go.Figure(data=go.Heatmap(
                z=micro_data['spectrogram'],
                x=micro_data['time'],
                y=micro_data['frequencies'] / 1000,  # 转换为kHz
                colorscale='Jet',
                colorbar=dict(title='幅度'),
                hovertemplate='时间: %{x:.2f}s<br>频率: %{y:.1f}kHz<br>幅度: %{z:.2f}<extra></extra>'
            ))
            
            # 添加周期标注线
            for i in range(1, int(2.0 / micro_data['rotation_period']) + 1):
                t_line = i * micro_data['rotation_period']
                if t_line < 2.0:
                    fig.add_vline(x=t_line, line_dash="dash", line_color="white", opacity=0.5)
            
            fig.update_layout(
                title=f"微多普勒时频图 (Spectrogram)<br><sub>叶尖速度: {micro_data['blade_tip_velocity']:.1f} m/s | 旋转周期: {micro_data['rotation_period']:.3f}s</sub>",
                xaxis_title="时间 (s)",
                yaxis_title="多普勒频率 (kHz)",
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.markdown("#### 📖 时频图解读")
            st.markdown(f"""
            **图中特征:**
            
            🎯 **中心亮带** (0 kHz附近)
            - 塔筒和轮毂的回波
            - 多普勒频移接近零
            
            🌊 **正弦调制曲线** 
            - 叶片旋转产生的微多普勒
            - 峰值对应叶尖朝向/背向雷达
            - 谷值对应叶片垂直于视线
            
            ⚡ **多叶片干涉**
            - {num_blades_display}个叶片产生{num_blades_display}组调制曲线
            - 相位差{360//num_blades_display}°
            
            📏 **周期特征**
            - 白色虚线标记旋转周期
            - 周期 = {micro_data['rotation_period']:.3f}s
            """)
    
    # Tab 3: 盲速与模糊分析
    with doppler_tabs[2]:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 🎯 盲速分析")
            
            # 盲速参数
            blind_v = getattr(doppler, 'blind_velocity', 0)
            if blind_v > 0:
                st.markdown(f"""
                | 参数 | 数值 | 说明 |
                |------|------|------|
                | **第一盲速** | {blind_v:.1f} m/s | 速度模糊间隔 |
                | **不模糊速度** | ±{getattr(doppler, 'unambiguous_velocity', blind_v/2):.1f} m/s | 无模糊测量范围 |
                | **多普勒分辨率** | {getattr(doppler, 'doppler_resolution', 0):.2f} Hz | 最小可分辨频差 |
                | **速度分辨率** | {getattr(doppler, 'doppler_resolution', 0) * 0.1:.2f} m/s | 等效速度分辨率 |
                """)
            else:
                # 使用默认值
                blind_v = 150.0  # 假设第一盲速
                unambiguous_v = 75.0
                st.markdown(f"""
                | 参数 | 数值 | 说明 |
                |------|------|------|
                | **第一盲速** | {blind_v:.1f} m/s | 速度模糊间隔 |
                | **不模糊速度** | ±{unambiguous_v:.1f} m/s | 无模糊测量范围 |
                | **速度分辨率** | 0.5 m/s | 等效速度分辨率 |
                """)
            
            st.info("""
            💡 **盲速现象**: 当目标径向速度等于盲速的整数倍时，
            目标回波会落入多普勒滤波器的零陷而被抑制，导致检测丢失。
            """)
        
        with col2:
            st.markdown("#### 📊 速度模糊图")
            
            # 绘制速度模糊图
            velocities = np.linspace(-200, 200, 401)  # 速度范围 ±200 m/s
            
            # 计算模糊速度谱 (假设PRF导致的周期性模糊)
            v_blind = getattr(doppler, 'blind_velocity', 150.0)
            ambiguity = np.abs(np.sinc(velocities / v_blind))  # sinc函数模拟模糊
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=velocities, y=ambiguity,
                mode='lines',
                name='速度模糊函数',
                line=dict(color='blue', width=2)
            ))
            
            # 标记盲速位置
            for n in [-2, -1, 0, 1, 2]:
                v_n = n * v_blind
                if -200 <= v_n <= 200:
                    fig.add_vline(x=v_n, line_dash="dash", line_color="red", opacity=0.5)
            
            # 标记风机杂波速度范围
            clutter_v_max = doppler.velocity_spread if doppler.velocity_spread > 0 else 50.0
            fig.add_vrect(
                x0=-clutter_v_max, x1=clutter_v_max,
                fillcolor="yellow", opacity=0.2,
                layer="below", line_width=0,
                annotation_text="风机杂波区", annotation_position="top"
            )
            
            fig.update_layout(
                title="速度模糊函数与盲速",
                xaxis_title="目标速度 (m/s)",
                yaxis_title="模糊程度",
                height=300,
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # Tab 4: MTI/MTD滤波器性能
    with doppler_tabs[3]:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("#### 🔧 MTI/MTD滤波器速度响应")
            
            # 生成MTI滤波器速度响应曲线
            velocities = np.linspace(-100, 100, 201)  # 速度范围
            
            # 单延迟对消器 (MTI) 响应
            # H(f) = 2|sin(πf/f_r)|, 其中f_r是PRF
            prf = 1000  # 假设PRF
            mti_response = np.abs(2 * np.sin(np.pi * velocities / 75))  # 简化的MTI响应
            mti_response = np.clip(mti_response, 0, 2)
            
            # MTD (多普勒滤波器组) 响应 - 示例一个滤波器
            mtd_center = 30  # 滤波器中心速度
            mtd_bw = 10      # 滤波器带宽
            mtd_response = np.exp(-((velocities - mtd_center) / (mtd_bw / 2.355))**2)
            
            fig = go.Figure()
            
            # MTI响应
            fig.add_trace(go.Scatter(
                x=velocities, y=mti_response,
                mode='lines',
                name='MTI滤波器 (凹口型)',
                line=dict(color='red', width=2)
            ))
            
            # MTD滤波器响应
            fig.add_trace(go.Scatter(
                x=velocities, y=mtd_response,
                mode='lines',
                name=f'MTD滤波器 ({mtd_center}m/s)',
                line=dict(color='green', width=2)
            ))
            
            # 标记凹口宽度
            notch_width = getattr(doppler, 'notch_width', 5.0)
            fig.add_vrect(
                x0=-notch_width/2, x1=notch_width/2,
                fillcolor="red", opacity=0.1,
                layer="below", line_width=0,
                annotation_text="MTI零速凹口", annotation_position="top left"
            )
            
            # 标记风机杂波速度
            clutter_v = doppler.velocity_spread if doppler.velocity_spread > 0 else 50.0
            fig.add_vrect(
                x0=-clutter_v, x1=clutter_v,
                fillcolor="orange", opacity=0.1,
                layer="below", line_width=0,
                annotation_text="风机杂波展宽", annotation_position="top right"
            )
            
            fig.update_layout(
                title="MTI/MTD滤波器速度响应特性",
                xaxis_title="目标径向速度 (m/s)",
                yaxis_title="滤波器增益 (归一化)",
                height=350,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.markdown("#### 📋 滤波器性能指标")
            
            csr = getattr(doppler, 'csr_improvement', 35.0)
            notch = getattr(doppler, 'notch_width', 5.0)
            
            st.markdown(f"""
            **MTI性能:**
            - 杂波抑制比 (CSR): **{csr:.1f} dB**
            - 零速凹口宽度: **±{notch/2:.1f} m/s**
            - 改善因子恶化: **{doppler.mti_degradation:.1f} dB**
            
            **MTD性能:**
            - 滤波器数量: 8-16个
            - 多普勒分辨率: 根据PRF
            - 信杂比改善: **{csr + 10:.1f} dB**
            
            **风机影响:**
            - 由于风机杂波具有多普勒展宽，
              传统的零速MTI无法完全抑制
            - 部分杂波会泄漏到相邻的多普勒通道
            """)
            
            if doppler.mti_degradation > 5:
                st.warning(f"⚠️ MTI性能严重恶化 ({doppler.mti_degradation:.1f} dB)，建议采用自适应MTI或MTD技术")
            elif doppler.mti_degradation > 3:
                st.info(f"ℹ️ MTI性能中度恶化 ({doppler.mti_degradation:.1f} dB)，需要关注低速目标检测")
            else:
                st.success(f"✅ MTI性能良好 ({doppler.mti_degradation:.1f} dB)")


def create_gauge_chart(title, value, threshold, unit, color):
    """创建仪表盘图表 - 显示实际误差值和风险等级"""
    
    # 计算风险等级（0-100%），误差越大风险越高
    # 当误差 <= 阈值时，风险为0%
    # 当误差 > 阈值时，风险按比例增加，最大100%
    if threshold > 0:
        if value <= threshold:
            risk_percentage = 0
        else:
            # 计算超出阈值的比例，使用对数压缩避免超大值
            ratio = value / threshold
            # 使用对数映射：ratio=2->30%, ratio=5->50%, ratio=10->70%, ratio=100->100%
            risk_percentage = min(100, 30 + 35 * np.log10(ratio))
    else:
        risk_percentage = 0
    
    # 确定显示范围：最大值至少是阈值的2倍或实际误差的1.2倍
    display_max = max(threshold * 2, value * 1.2, threshold * 1.5)
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number={'suffix': unit, 'font': {'size': 20}, 'valueformat': '.2f' if value < 10 else '.1f'},
        title={'text': title, 'font': {'size': 14}},
        gauge={
            'axis': {
                'range': [0, display_max],
                'tickwidth': 2,
                'tickcolor': "gray",
                'tickfont': {'size': 10}
            },
            'bar': {'color': color, 'thickness': 0.75},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [0, threshold * 0.5], 'color': '#ccffcc'},   # 绿色 - 优秀 (<50%阈值)
                {'range': [threshold * 0.5, threshold], 'color': '#ffffcc'},  # 黄色 - 良好 (50%-100%阈值)
                {'range': [threshold, display_max], 'color': '#ffcccc'}  # 红色 - 超标 (>阈值)
            ],
            'threshold': {
                'line': {'color': "red", 'width': 3},
                'thickness': 0.8,
                'value': threshold  # 阈值线位置
            }
        }
    ))
    
    fig.update_layout(
        height=280,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor="white",
        font={'size': 12}
    )
    
    return fig, risk_percentage


def render_accuracy_results(result):
    """渲染精度分析结果 - 单独分析每个精度指标"""
    accuracy = result.accuracy
    
    # 归一化阈值定义（基于典型雷达性能）
    angle_threshold = 2.0    # 度 - 测角误差阈值
    range_threshold = 50.0   # 米 - 测距误差阈值
    velocity_threshold = 5.0 # 米/秒 - 测速误差阈值
    
    st.subheader("📊 精度指标单独分析")
    st.info("""
    📖 **仪表盘说明**：
    - **指针位置**：显示实际误差值
    - **红色竖线**：表示精度阈值（允许的最大误差）
    - **绿色区域** (0-50%阈值)：优秀，误差远小于阈值
    - **黄色区域** (50%-100%阈值)：良好，误差接近但未超阈值
    - **红色区域** (>阈值)：超标，误差超过允许范围
    """)
    
    # 创建三个独立的仪表盘
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**🎯 测角精度**")
        angle_fig, angle_pct = create_gauge_chart(
            f"测角误差",
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
            f"测距误差",
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
            f"测速误差",
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
    
    # 绕射损耗可视化
    st.subheader("绕射损耗可视化")
    
    if not diffraction.terrain_shadowing:
        st.info("暂无风机绕射数据")
        return
    
    # 创建简化直观的柱状图
    st.markdown("### 📊 各风机绕射损耗对比")
    
    # 准备数据
    turbine_names = [item['turbine_name'] for item in diffraction.terrain_shadowing]
    losses = [item['knife_edge_loss'] for item in diffraction.terrain_shadowing]
    distances = [item['distance'] / 1000 for item in diffraction.terrain_shadowing]  # 转换为km
    blockage_ratios = [item['blockage_ratio'] for item in diffraction.terrain_shadowing]
    
    # 创建双轴图：柱状图显示损耗，折线显示距离
    fig = go.Figure()
    
    # 柱状图 - 绕射损耗
    colors = ['🟢' if l < 5 else '🟡' if l < 15 else '🔴' for l in losses]
    bar_colors = ['#4CAF50' if l < 5 else '#FFC107' if l < 15 else '#F44336' for l in losses]
    
    # 根据风机数量动态调整柱子宽度，避免风机少时柱子太宽
    num_turbines = len(turbine_names)
    bar_width = min(0.4, 0.8 / num_turbines) if num_turbines > 0 else 0.4
    
    fig.add_trace(go.Bar(
        x=turbine_names,
        y=losses,
        name='绕射损耗 (dB)',
        marker_color=bar_colors,
        width=bar_width,  # 限制柱子最大宽度
        text=[f"{l:.1f} dB" for l in losses],
        textposition='outside',
        hovertemplate='<b>%{x}</b><br>绕射损耗: %{y:.1f} dB<extra></extra>'
    ))
    
    # 折线 - 距离
    fig.add_trace(go.Scatter(
        x=turbine_names,
        y=distances,
        name='距离 (km)',
        mode='lines+markers+text',
        line=dict(color='#2196F3', width=2),
        marker=dict(size=8, color='#2196F3'),
        text=[f"{d:.1f}km" for d in distances],
        textposition='top center',
        textfont=dict(size=14, color='white'),
        yaxis='y2',
        hovertemplate='<b>%{x}</b><br>距离: %{y:.1f} km<extra></extra>'
    ))
    
    fig.update_layout(
        title=dict(
            text="各风机绕射损耗与距离关系",
            font=dict(size=16)
        ),
        xaxis_title="风机",
        yaxis=dict(
            title="绕射损耗 (dB)",
            # titlefont=dict(color='#333'),
            tickfont=dict(color='#333'),
            range=[0, max(losses) * 1.3]
        ),
        yaxis2=dict(
            title="距离 (km)",
            # titlefont=dict(color='#2196F3'),
            tickfont=dict(color='#2196F3'),
            overlaying='y',
            side='right',
            range=[0, max(distances) * 1.5]
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5
        ),
        barmode='group',
        height=400,
        showlegend=True
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # 风险等级说明
    st.markdown("""
    **📈 绕射损耗风险等级：**
    - 🟢 **绿色 (< 5 dB)**：低风险，对雷达性能影响较小
    - 🟡 **黄色 (5-15 dB)**：中等风险，雷达性能有一定下降
    - 🔴 **红色 (> 15 dB)**：高风险，雷达探测能力严重受限
    """)
    
    # 详细数据表格
    with st.expander("📋 查看详细数据"):
        df = pd.DataFrame({
            '风机名称': turbine_names,
            '距离 (km)': [f"{d:.2f}" for d in distances],
            '绕射损耗 (dB)': [f"{l:.1f}" for l in losses],
            '遮挡比': [f"{b:.2f}" for b in blockage_ratios],
            '风险等级': ['🟢 低' if l < 5 else '🟡 中' if l < 15 else '🔴 高' for l in losses]
        })
        st.dataframe(df, use_container_width=True, hide_index=True)


def calculate_turbine_rcs(turbine, azimuth_deg, elevation_deg=0.0, frequency_ghz=3.0):
    """
    计算单个风机的RCS值
    
    基于物理模型：
    - 塔筒：金属圆柱体，使用圆柱体RCS公式
    - 叶片：玻璃钢材质，RCS较低
    
    Args:
        turbine: 风机对象
        azimuth_deg: 方位角（度）
        elevation_deg: 俯仰角（度，默认为0）
        frequency_ghz: 雷达频率（GHz）
    
    Returns:
        rcs_dbsm: RCS值（dBm²）
    """
    import numpy as np
    
    # 波长计算
    c = 3e8  # 光速 m/s
    wavelength = c / (frequency_ghz * 1e9)  # 波长（米）
    k = 2 * np.pi / wavelength  # 波数
    
    # 转换角度为弧度
    azimuth = np.radians(azimuth_deg)
    elevation = np.radians(elevation_deg)
    
    # 塔筒参数
    tower_height = turbine.tower_height_m
    tower_diameter = turbine.tower_diameter_m
    
    # 叶片参数
    blade_length = turbine.blade_length_m
    blade_width = 3.0  # 叶片宽度约3米
    num_blades = turbine.blade_count
    
    # ========== 塔筒RCS计算（金属圆柱体）==========
    # 塔筒等效圆柱体RCS
    # 使用圆柱体RCS近似公式
    
    # 计算有效照射面积
    # 俯仰角影响：仰视角度越大，看到的塔筒侧面越少
    elevation_factor = np.abs(np.cos(elevation))
    
    # 塔筒物理RCS（圆柱体镜面反射 + 边缘绕射）
    # 镜面反射分量（垂直入射时最大）
    if np.abs(np.cos(azimuth)) > 0.1:  # 避免除零
        specular_rcs = (k * tower_diameter * tower_height**2 / 2) * np.abs(np.cos(azimuth)) * elevation_factor
    else:
        specular_rcs = 0
    
    # 边缘绕射分量
    edge_rcs = (tower_height * tower_diameter / 4) * np.abs(np.sin(azimuth))
    
    # 塔筒总RCS（金属材质，反射强）
    tower_rcs_linear = specular_rcs + edge_rcs + 0.1  # 最小值避免log(0)
    
    # 塔筒RCS波动（模拟表面粗糙度和结构细节）
    # 使用正弦函数模拟周期性波动，加入随机分量
    fluctuation = 1 + 0.3 * np.sin(4 * azimuth) + 0.2 * np.sin(8 * azimuth)
    # 方位角相关调制（塔筒侧面vs正面）
    azimuth_modulation = 0.6 + 0.4 * np.abs(np.cos(azimuth))
    
    tower_rcs_linear *= fluctuation * azimuth_modulation
    
    # 频率影响：低频（VHF）RCS大，高频（Ku）RCS小
    # 这是由于高频在粗糙表面产生更多漫散射
    freq_factor_tower = (3.0 / frequency_ghz) ** 0.5  # 频率修正因子
    tower_rcs_linear *= freq_factor_tower
    
    # ========== 叶片RCS计算（玻璃钢材质）==========
    # 玻璃钢材质RCS比金属低很多（约-15到-20dB）
    material_loss_db = 18.0  # 玻璃钢相比金属的衰减
    
    # 叶片旋转产生的RCS调制
    blade_rotation_angle = np.radians(azimuth_deg * 2)  # 假设叶片旋转与方位角相关
    
    # 单个叶片RCS（平板近似）
    # 叶片在不同姿态下的RCS变化
    blade_aspect_angle = azimuth + blade_rotation_angle
    
    # 叶片镜面反射（当叶片垂直于雷达视线时最强）
    blade_specular = (k * blade_length**2 * blade_width / (4 * np.pi)) * \
                     np.abs(np.cos(blade_aspect_angle))**2 * np.abs(np.cos(elevation))
    
    # 叶片边缘散射
    blade_edge = blade_length * blade_width * 0.1 * np.abs(np.sin(blade_aspect_angle))
    
    # 单个叶片RCS
    single_blade_rcs = blade_specular + blade_edge + 0.05
    
    # 多叶片干涉（3个叶片在空间中分散）
    # 叶片间角度间隔：120度
    blade_separation = 2 * np.pi / num_blades
    
    # 考虑叶片之间相对位置导致的相干/非相干散射
    total_blade_rcs = 0
    for i in range(num_blades):
        blade_angle_offset = i * blade_separation
        blade_phase = k * blade_length * np.sin(elevation) * np.cos(blade_rotation_angle + blade_angle_offset)
        interference_factor = 1 + 0.5 * np.cos(blade_phase)  # 干涉因子
        total_blade_rcs += single_blade_rcs * interference_factor
    
    # 玻璃钢材质衰减
    blade_rcs_linear = total_blade_rcs / num_blades * (10 ** (-material_loss_db / 10))
    
    # 频率对叶片RCS的影响（高频在复合材料中衰减更大）
    freq_factor_blade = (3.0 / frequency_ghz) ** 0.3
    blade_rcs_linear *= freq_factor_blade
    
    # ========== 总RCS计算 ==========
    # 相干叠加（塔筒和叶片在不同位置，近似非相干叠加）
    total_rcs_linear = tower_rcs_linear + blade_rcs_linear
    
    # 转换为dBm²
    total_rcs_dbsm = 10 * np.log10(total_rcs_linear)
    
    # 添加随机起伏（RCS闪烁）
    # 高频闪烁更明显
    scintillation_db = np.random.normal(0, 1.5 * (frequency_ghz / 3.0) ** 0.5)
    total_rcs_dbsm += scintillation_db
    
    return total_rcs_dbsm


def render_rcs_simulation():
    """渲染风机RCS仿真结果"""
    
    if not st.session_state.scene.turbines:
        st.warning("⚠️ 请先添加至少一台风机")
        return
    
    # 选择要仿真的风机
    turbine_names = [t.name for t in st.session_state.scene.turbines]
    selected_turbine_name = st.selectbox("选择要仿真的风机", turbine_names)
    selected_turbine = next(t for t in st.session_state.scene.turbines if t.name == selected_turbine_name)
    
    # 显示风机参数
    st.info(f"📍 **{selected_turbine.name}** 参数 | "
            f"型号: {selected_turbine.model} | "
            f"塔高: {selected_turbine.tower_height_m}m | "
            f"叶片长: {selected_turbine.blade_length_m}m | "
            f"塔筒直径: {selected_turbine.tower_diameter_m}m | "
            f"叶片数: {selected_turbine.blade_count}")
    
    # 仿真配置
    col1, col2 = st.columns(2)
    with col1:
        elevation_angle = st.number_input("俯仰角 (°)", min_value=-30.0, max_value=30.0, value=0.0, step=1.0,
                                         help="0°表示水平照射，正值为仰角，负值为俯角")
    with col2:
        st.markdown("**仿真设置**：方位间隔 1°，覆盖 0°-360°")
    
    # 雷达波段配置
    bands = {
        'VHF': {'freq_ghz': 0.15, 'color': '#8B0000', 'desc': 'VHF (30-300MHz)'},
        'L': {'freq_ghz': 1.5, 'color': '#FF0000', 'desc': 'L波段 (1-2GHz)'},
        'S': {'freq_ghz': 3.0, 'color': '#FF8C00', 'desc': 'S波段 (2-4GHz)'},
        'C': {'freq_ghz': 5.5, 'color': '#FFD700', 'desc': 'C波段 (4-8GHz)'},
        'X': {'freq_ghz': 10.0, 'color': '#32CD32', 'desc': 'X波段 (8-12GHz)'},
        'Ku': {'freq_ghz': 15.0, 'color': '#1E90FF', 'desc': 'Ku波段 (12-18GHz)'}
    }
    
    # 选择要显示的波段
    selected_bands = st.multiselect(
        "选择要仿真的雷达波段",
        list(bands.keys()),
        default=['S', 'C', 'X', 'Ku'],
        format_func=lambda x: bands[x]['desc']
    )
    
    if not selected_bands:
        st.info("请至少选择一个波段进行仿真")
        return
    
    # 计算RCS数据
    azimuths = np.arange(0, 361, 1)  # 0-360度，间隔1度
    
    with st.spinner("正在计算RCS..."):
        rcs_data = {}
        for band_name in selected_bands:
            band = bands[band_name]
            rcs_values = []
            for azimuth in azimuths:
                rcs = calculate_turbine_rcs(
                    selected_turbine,
                    azimuth,
                    elevation_angle,
                    band['freq_ghz']
                )
                rcs_values.append(rcs)
            rcs_data[band_name] = rcs_values
    
    # 创建极坐标图
    fig = go.Figure()
    
    for band_name in selected_bands:
        band = bands[band_name]
        fig.add_trace(go.Scatterpolar(
            r=rcs_data[band_name],
            theta=azimuths,
            mode='lines',
            name=band['desc'],
            line=dict(color=band['color'], width=2),
            hovertemplate='方位: %{theta}°<br>RCS: %{r:.1f} dBm²<extra>' + band_name + '波段</extra>'
        ))
    
    # 更新布局
    max_rcs = max([max(rcs_data[b]) for b in selected_bands]) * 1.1
    
    fig.update_layout(
        title=dict(
            text=f'风力涡轮机RCS极坐标图<br><sub>{selected_turbine.name} | 俯仰角 {elevation_angle}°</sub>',
            font=dict(size=16)
        ),
        polar=dict(
            radialaxis=dict(
                visible=True,
                title=dict(
                    text='RCS (dBm²)',
                    font=dict(size=16, color='black')
                ),
                range=[0, max_rcs],
                # 白色圆环网格线配置
                gridcolor='white',
                gridwidth=2,
                tickfont=dict(color='black', size=16),
                tickvals=np.linspace(0, max_rcs, 6),
                linecolor='white',
                linewidth=2
            ),
            angularaxis=dict(
                tickmode='array',
                tickvals=[0, 45, 90, 135, 180, 225, 270, 315],
                ticktext=['0°', '45°', '90°', '135°', '180°', '225°', '270°', '315°'],
                direction='clockwise',
                rotation=90,  # 0度在上方
                gridcolor='white',
                gridwidth=1.5,
                tickfont=dict(color='black', size=14)
            ),
            # 深蓝/灰蓝色背景，类似气象雷达
            bgcolor='rgba(25, 50, 80, 0.9)'
        ),
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.05,
            bgcolor='rgba(255, 255, 255, 0.9)',
            bordercolor='gray',
            borderwidth=1
        ),
        height=650,
        template='plotly_dark',
        paper_bgcolor='rgba(240, 245, 250, 1)',
        plot_bgcolor='rgba(240, 245, 250, 1)'
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # RCS统计信息
    st.subheader("RCS统计信息")
    
    stats_data = []
    for band_name in selected_bands:
        rcs_values = np.array(rcs_data[band_name])
        stats_data.append({
            '波段': band_name,
            '平均RCS (dBm²)': f"{np.mean(rcs_values):.1f}",
            '最大RCS (dBm²)': f"{np.max(rcs_values):.1f}",
            '最小RCS (dBm²)': f"{np.min(rcs_values):.1f}",
            'RCS波动 (dB)': f"{np.std(rcs_values):.1f}"
        })
    
    stats_df = pd.DataFrame(stats_data)
    st.dataframe(stats_df, use_container_width=True, hide_index=True)
    
    # RCS物理说明
    with st.expander("📖 RCS仿真说明", expanded=False):
        st.markdown("""
        **RCS（雷达散射截面积）仿真原理：**
        
        1. **塔筒RCS**（金属材质）：
           - 采用圆柱体RCS模型
           - 镜面反射分量：垂直入射时最强
           - 边缘绕射分量：侧面入射时贡献大
           - 低频（VHF/L）RCS较大，高频衰减较慢
        
        2. **叶片RCS**（玻璃钢材质）：
           - 玻璃钢相比金属RCS低约18dB
           - 采用平板近似模型
           - 考虑叶片旋转姿态和叶片间干涉
           - 高频衰减更明显（复合材料吸收）
        
        3. **频率特性**：
           - **VHF/L波段**：RCS最大，穿透性强，结构谐振明显
           - **S/C波段**：中等RCS，工程常用频段
           - **X/Ku波段**：RCS较小，表面粗糙度影响大
        
        4. **方位调制特性**：
           - **塔筒正面（0°, 180°）**：镜面反射峰值区域，RCS通常较大
           - **塔筒侧面（90°, 270°）**：边缘绕射主导区域，RCS相对较小
           - 但具体数值还受**俯仰角**和**叶片姿态**影响
        
        5. **为什么某些角度RCS较小？**
           - **俯仰角影响**：当俯仰角不为0°时，塔筒的有效照射投影面积减小
           - **叶片遮挡效应**：3个叶片以120°间隔分布，某些方位角下叶片会遮挡塔筒
           - **相干抵消**：塔筒和叶片的散射场可能发生相位相消干涉
           - **姿态调制**：叶片旋转导致周期性RCS起伏，某些方位正好处于波谷
           - **边缘方向（90°, 270°附近）**：圆柱体侧面回波较弱，主要靠边缘绕射
        """)


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
    tabs = st.tabs(["🚫 遮挡分析", "📡 散射分析", "🌊 多普勒分析", "🎯 精度分析", "🌊 多径效应", "🗻 绕射损耗", "📊 RCS仿真"])
    
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
    
    with tabs[6]:
        render_rcs_simulation()


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
    
    # 等值线图显示控制
    show_contour = st.checkbox("🔥 显示探测性能等值线图层", value=True, key="show_contour_checkbox")
    
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
            
            # 渲染地图（传入等值线参数）
            with map_placeholder.container():
                render_circular_motion_map(
                    sim, inner_pos, outer_pos, center_lat, center_lon,
                    show_detection_contour=show_contour,
                    altitude_m=altitude_m,
                    rcs_dbsm=rcs_dbsm
                )
            
            # 渲染指标
            with metrics_placeholder.container():
                render_circular_motion_metrics(inner_pos, outer_pos, inner_metrics, outer_metrics)
            
            # 自动刷新
            time.sleep(0.5)
            st.experimental_rerun()
    else:
        # 未运行仿真时，显示静态地图（只显示等值线）
        if show_contour:
            sim = CircularMotionSimulator(
                config=CircularMotionConfig(center_lat=center_lat, center_lon=center_lon),
                radar=radar,
                turbines=turbines
            )
            render_circular_motion_map(
                sim, None, None, center_lat, center_lon,
                show_detection_contour=True,
                altitude_m=altitude_m,
                rcs_dbsm=rcs_dbsm
            )
        else:
            st.info("👆 点击'开始仿真'按钮启动圆周运动仿真，或勾选上方'显示探测性能等值线图层'查看覆盖范围")


def calculate_detection_probability_at_point(radar, turbines, lat, lon, altitude_m, rcs_dbsm):
    """
    计算指定位置的探测概率
    
    Args:
        radar: 雷达配置
        turbines: 风机列表
        lat, lon: 目标位置
        altitude_m: 目标高度
        rcs_dbsm: 目标RCS
        
    Returns:
        detection_probability: 探测概率 (0-1)
        snr_db: 信噪比 (dB)
        is_blocked: 是否被遮挡
    """
    from models.target import TargetConfig
    from engine.circular_motion_sim import TargetState, CircularMotionSimulator
    
    # 计算距离和方位
    distance_m = calculate_distance(radar.latitude, radar.longitude, lat, lon)
    bearing = calculate_bearing(radar.latitude, radar.longitude, lat, lon)
    
    # 检查是否在雷达最大探测范围内
    max_range_m = radar.max_range_km * 1000
    if distance_m > max_range_m:
        return 0.0, -999.0, False
    
    # 检查是否在波束范围内
    beam_center = radar.beam_direction_deg
    beam_width = radar.beamwidth_deg
    angle_diff = abs(bearing - beam_center)
    angle_diff = min(angle_diff, 360 - angle_diff)
    
    if angle_diff > beam_width / 2:
        return 0.0, -999.0, False
    
    # 检查是否被风机遮挡
    is_blocked = False
    for turbine in turbines:
        # 简化的遮挡检测：如果目标在风机后方且角度接近
        turbine_bearing = calculate_bearing(radar.latitude, radar.longitude, 
                                           turbine.latitude, turbine.longitude)
        turbine_distance = calculate_distance(radar.latitude, radar.longitude,
                                             turbine.latitude, turbine.longitude)
        
        # 如果风机在雷达和目标之间
        angle_diff_to_turbine = abs(bearing - turbine_bearing)
        angle_diff_to_turbine = min(angle_diff_to_turbine, 360 - angle_diff_to_turbine)
        
        if angle_diff_to_turbine < 2.0 and distance_m > turbine_distance:
            is_blocked = True
            break
    
    # 计算SNR（简化雷达方程）
    wavelength = radar.get_wavelength()
    snr_base = (radar.power_kw * 1000 * 
                (10 ** (radar.antenna_gain_dbi / 10)) ** 2 * 
                wavelength ** 2 * 
                (10 ** (rcs_dbsm / 10))) / (distance_m ** 4)
    
    snr_db = 10 * np.log10(snr_base) + 100
    
    if is_blocked:
        snr_db -= 20.0
    
    # 波束方向图影响
    beam_factor = np.exp(-2.776 * (angle_diff / (beam_width / 2)) ** 2)
    snr_db += 10 * np.log10(beam_factor)
    
    # 计算探测概率
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
    
    return detection_probability, snr_db, is_blocked
    
    # 生成网格数据
    with st.spinner("正在计算探测性能分布..."):
        grid_data = generate_detection_contour_data(
            radar, turbines, center_lat, center_lon,
            radius_km=radar.max_range_km * 0.8,  # 使用雷达最大探测距离的80%
            grid_size=60,
            altitude_m=altitude_m,
            rcs_dbsm=rcs_dbsm
        )
    
    # 选择显示指标
    metric_option = st.radio(
        "选择显示指标",
        ["探测概率", "信噪比 (SNR)"],
        horizontal=True,
        key="contour_metric"
    )
    
    if metric_option == "探测概率":
        z_data = grid_data['detection_probs']
        colorscale = [
            [0, 'rgba(0,0,100,0.3)'],      # 深蓝 - 无探测
            [0.2, 'rgba(0,100,255,0.4)'],  # 蓝
            [0.4, 'rgba(0,255,255,0.5)'],  # 青
            [0.6, 'rgba(0,255,0,0.5)'],    # 绿
            [0.8, 'rgba(255,255,0,0.6)'],  # 黄
            [1, 'rgba(255,0,0,0.7)']       # 红 - 高探测概率
        ]
        zmin, zmax = 0, 1
        colorbar_title = "探测概率"
    else:
        z_data = grid_data['snr_values']
        colorscale = "Viridis"
        zmin, zmax = -30, 40
        colorbar_title = "SNR (dB)"
    
    # 创建等值线图
    fig = go.Figure()
    
    # 添加等值线
    fig.add_trace(go.Contour(
        z=z_data,
        x=grid_data['lons'],
        y=grid_data['lats'],
        colorscale=colorscale,
        contours=dict(
            start=zmin,
            end=zmax,
            size=(zmax - zmin) / 10,
            showlabels=True,
            labelfont=dict(size=10, color='white')
        ),
        colorbar=dict(
            title=colorbar_title,
            # titleside='right',
            thickness=20,
            len=0.8
        ),
        opacity=0.7,
        name='探测性能'
    ))
    
    # 添加雷达位置
    fig.add_trace(go.Scatter(
        x=[radar.longitude],
        y=[radar.latitude],
        mode='markers+text',
        marker=dict(size=15, color='red', symbol='x'),
        text=['雷达'],
        textposition='top center',
        name='雷达'
    ))
    
    # 添加风机位置
    if turbines:
        turbine_lons = [t.longitude for t in turbines]
        turbine_lats = [t.latitude for t in turbines]
        fig.add_trace(go.Scatter(
            x=turbine_lons,
            y=turbine_lats,
            mode='markers+text',
            marker=dict(size=10, color='white', symbol='diamond', 
                       line=dict(color='black', width=1)),
            text=[t.name for t in turbines],
            textposition='bottom center',
            name='风机'
        ))
    
    # 设置布局
    fig.update_layout(
        title=f"{metric_option}分布 (高度: {altitude_m}m, RCS: {rcs_dbsm}dBm²)",
        xaxis_title="经度",
        yaxis_title="纬度",
        height=600,
        showlegend=True,
        yaxis=dict(scaleanchor="x", scaleratio=1),  # 保持比例
        plot_bgcolor='rgba(240,240,240,0.5)'
    )
    

def generate_detection_contour_data(radar, turbines, center_lat, center_lon,
                                     radius_km=10, grid_size=50, altitude_m=1000, rcs_dbsm=10):
    """
    生成探测性能等值线数据用于PyDeck ContourLayer
    
    Returns:
        contour_data: 包含网格数据和等值线配置的字典
    """
    # 创建网格
    lat_range = radius_km / 111.0
    lon_range = radius_km / (111.0 * np.cos(np.radians(center_lat)))
    
    lats = np.linspace(center_lat - lat_range, center_lat + lat_range, grid_size)
    lons = np.linspace(center_lon - lon_range, center_lon + lon_range, grid_size)
    
    # 计算每个网格点的探测概率，生成2D数组
    detection_probs = np.zeros((grid_size, grid_size))
    
    for i, lat in enumerate(lats):
        for j, lon in enumerate(lons):
            prob, snr, is_blocked = calculate_detection_probability_at_point(
                radar, turbines, lat, lon, altitude_m, rcs_dbsm
            )
            detection_probs[i, j] = prob
    
    # 将网格数据转换为 ContourLayer 需要的格式
    # ContourLayer 需要一个包含所有网格点的数组，每个点包含 [lon, lat, value]
    grid_points = []
    for i, lat in enumerate(lats):
        for j, lon in enumerate(lons):
            grid_points.append([lon, lat, detection_probs[i, j]])
    
    return {
        'grid_points': grid_points,
        'bounds': [
            center_lon - lon_range,  # minX
            center_lat - lat_range,  # minY
            center_lon + lon_range,  # maxX
            center_lat + lat_range   # maxY
        ],
        'grid_size': [grid_size, grid_size]
    }


def render_circular_motion_map(sim, inner_pos, outer_pos, center_lat, center_lon, 
                                show_detection_contour=True, altitude_m=1000, rcs_dbsm=10):
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
        'angle': 0,
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
            'angle': 0,
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
        'angle': 0,
        'color': [128, 128, 128],
        'icon': get_icon_data('circle')
    })
    
    # 添加目标（带旋转角度）
    if inner_pos:
        # 计算飞机图标旋转角度（heading是正北顺时针，pydeck的angle是东逆时针，需要转换）
        # pydeck的0度指向东（右侧），需要转换：angle = 90 - heading
        inner_angle = (90 - inner_pos['heading']) % 360
        map_data.append({
            'lat': inner_pos['lat'],
            'lon': inner_pos['lon'],
            'name': inner_pos['label'],
            'type': f"内圈目标 | 探测概率: {inner_pos['detection_probability']*100:.1f}% | SNR: {inner_pos['snr_db']:.1f}dB | 航向: {inner_pos['heading']:.1f}°",
            'size': 18,
            'angle': inner_angle,
            'color': [0, 255, 255] if not inner_pos['is_blocked'] else [255, 0, 0],
            'icon': get_icon_data('airport')
        })
    
    if outer_pos:
        # 计算飞机图标旋转角度
        outer_angle = (90 - outer_pos['heading']) % 360
        map_data.append({
            'lat': outer_pos['lat'],
            'lon': outer_pos['lon'],
            'name': outer_pos['label'],
            'type': f"外圈目标 | 探测概率: {outer_pos['detection_probability']*100:.1f}% | SNR: {outer_pos['snr_db']:.1f}dB | 航向: {outer_pos['heading']:.1f}°",
            'size': 18,
            'angle': outer_angle,
            'color': [255, 165, 0] if not outer_pos['is_blocked'] else [255, 0, 0],
            'icon': get_icon_data('airport')
        })
    
    df = pd.DataFrame(map_data)
    
    # Mapbox API密钥
    MAPBOX_API_KEY = "***REMOVED***"
    
    # 创建基础图层列表
    layers = []
    
    # 添加探测性能热力图层（使用HeatmapLayer）
    if show_detection_contour:
        contour_data = generate_detection_contour_data(
            radar, turbines, center_lat, center_lon,
            radius_km=radar.max_range_km * 0.6,  # 使用雷达最大探测距离的60%
            grid_size=100,  # 增加网格密度使热力图更平滑
            altitude_m=altitude_m,
            rcs_dbsm=rcs_dbsm
        )
        
        # 使用HeatmapLayer显示探测性能热力图
        # 将数据转换为 {position: [lon, lat], weight: prob} 格式
        heatmap_data = []
        for point in contour_data['grid_points']:
            heatmap_data.append({
                'position': [point[0], point[1]],  # [lon, lat]
                'weight': point[2]  # detection probability
            })
        
        heatmap_layer = pydeck.Layer(
            'HeatmapLayer',
            data=heatmap_data,
            id='detection-heatmap',
            get_position='position',
            get_weight='weight',
            # 热力图半径 - 适当大小让点融合成云图效果
            radius_pixels=100,
            # 颜色映射：气象雷达风格，从红色(低探测)到绿色(高探测)
            color_range=[
                [192, 192, 192, 180],       # 绿色 - 无探测/极低
                [255, 0, 0, 180],       # 红色 - 低探测
                [255, 165, 0, 180],     # 橙色 - 较低
                [255, 255, 0, 180],     # 黄色 - 中等
                [173, 255, 47, 180],    # 黄绿 - 较高
                [0, 255, 0, 200],       # 绿色 - 高探测
            ],
            # 强度 - 降低使颜色过渡更平滑
            intensity=0.3,
            threshold=0.05,
            opacity=0.6
        )
        layers.append(heatmap_layer)
    
    # 添加圆周轨迹
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
        layers.append(inner_path_layer)
    
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
        layers.append(outer_path_layer)
    
    # 创建图标图层（放在最上层）
    icon_layer = pydeck.Layer(
        'IconLayer',
        data=df,
        get_icon='icon',
        get_size='size',
        get_color="color",
        get_angle='angle',
        size_scale=2,
        get_position=['lon', 'lat'],
        pickable=True,
        opacity=1.0
    )
    layers.append(icon_layer)
    
    # 设置视图
    view_state = pydeck.ViewState(
        latitude=center_lat,
        longitude=center_lon,
        zoom=11,
        pitch=0,  # 2D俯视视角
        bearing=0
    )
    
    # 创建地图
    r = pydeck.Deck(
        layers=layers,
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
    
    # 显示图例
    if show_detection_contour:
        st.markdown("""
        **探测性能热力图图例（气象雷达风格）：**
        - 🟢 **绿色**：探测概率 80-100%（高探测性能）
        - 🟡 **黄绿色**：探测概率 60-80%（较高探测性能）
        - **黄色**：探测概率 40-60%（中等探测性能）
        - 🟠 **橙色**：探测概率 20-40%（较低探测性能）
        - 🔴 **红色/深红**：探测概率 < 20%（无有效探测）
        
        *热力图以平滑渐变形式展示雷达探测性能分布，颜色从红色（低探测）过渡到绿色（高探测），类似气象雷达回波图，受雷达覆盖范围、波束方向和风机遮挡影响*
        """)


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
