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
from utils.geo_utils import calculate_distance, calculate_bearing

# 初始化session state
if 'scene' not in st.session_state:
    st.session_state.scene = Scene()
if 'evaluation_result' not in st.session_state:
    st.session_state.evaluation_result = None
if 'map_center' not in st.session_state:
    st.session_state.map_center = [39.9042, 120.4074]

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
            lat_offset = st.slider("纬度偏移 (km)", -10.0, 10.0, 1.0, 0.1)
        with col2:
            lon_offset = st.slider("经度偏移 (km)", -10.0, 10.0, 1.0, 0.1)
        
        # 计算实际坐标（简化：1度≈111km）
        radar = st.session_state.scene.radar
        turbine_lat = radar.latitude + lat_offset / 111
        turbine_lon = radar.longitude + lon_offset / (111 * np.cos(np.radians(radar.latitude)))
        
        st.info(f"📍 风机位置: 纬度 {turbine_lat:.6f}, 经度 {turbine_lon:.6f}")
    
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
        # st.rerun()


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
        
        with col2:
            target.altitude_m = st.number_input(
                "飞行高度 (m)",
                min_value=0.0, max_value=30000.0,
                value=type_defaults["altitude_m"], step=100.0
            )
            target.velocity_ms = st.number_input(
                "飞行速度 (m/s)",
                min_value=0.0, max_value=1000.0,
                value=type_defaults["velocity_ms"], step=10.0
            )


def render_turbine_list():
    """渲染风机列表"""
    st.subheader("📋 已添加风机")
    
    turbines = st.session_state.scene.turbines
    
    if not turbines:
        st.info("暂无风机，请在上方添加")
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
        st.rerun()


def render_map():
    """渲染地图视图"""
    st.subheader("🗺️ 场景地图")
    
    radar = st.session_state.scene.radar
    turbines = st.session_state.scene.turbines
    
    # 创建地图数据
    map_data = []
    
    # 添加雷达站
    map_data.append({
        'lat': radar.latitude,
        'lon': radar.longitude,
        'name': radar.name,
        'type': '雷达站',
        'size': 20,
        'color': 'red'
    })
    
    # 添加风机
    for t in turbines:
        map_data.append({
            'lat': t.latitude,
            'lon': t.longitude,
            'name': t.name,
            'type': f'风机 ({t.model})',
            'size': 10,
            'color': 'blue'
        })
    
    df = pd.DataFrame(map_data)
    
    # Mapbox API密钥
    MAPBOX_API_KEY = "***REMOVED***"
    
    # 颜色映射
    color_map = {
        'red': [255, 0, 0],
        'blue': [0, 0, 255]
    }
    
    # 准备图层数据
    if len(df) > 0:
        # 转换为PyDeck所需的格式
        df['radius'] = df['size'] * 50  # 缩放半径
        df['color'] = df['color'].map(lambda x: color_map.get(x, [128, 128, 128]))
        
        # 创建散点图层
        scatter_layer = pydeck.Layer(
            'ScatterplotLayer',
            data=df,
            get_position=['lon', 'lat'],
            get_radius='radius',
            get_fill_color='color',
            get_line_color=[0, 0, 0],
            get_line_width=1,
            pickable=True,
            opacity=0.8,
            stroked=True,
            filled=True,
            radius_scale=1,
            radius_min_pixels=3,
            radius_max_pixels=30
        )
        
        # 设置视图状态（以雷达位置为中心）
        zoom_level = 10 if not turbines else 9  # 有风机时缩小一些
        view_state = pydeck.ViewState(
            latitude=radar.latitude,
            longitude=radar.longitude,
            zoom=zoom_level,
            pitch=0,
            bearing=0
        )
        
        # 创建地图
        r = pydeck.Deck(
            layers=[scatter_layer],
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
        sector_df = pd.DataFrame(blocking.affected_sectors)
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
        turbine_df = pd.DataFrame(scattering.affected_turbines)
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


def render_accuracy_results(result):
    """渲染精度分析结果"""
    accuracy = result.accuracy
    
    # 指标卡片
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="测角偏差",
            value=f"{accuracy.angle_error:.3f}°",
            delta=f"降级 {accuracy.angle_degradation:.1f}%"
        )
    
    with col2:
        st.metric(
            label="测距偏差",
            value=f"{accuracy.range_error:.0f} m",
            delta=f"降级 {accuracy.range_degradation:.1f}%"
        )
    
    with col3:
        st.metric(
            label="测速偏差",
            value=f"{accuracy.velocity_error:.1f} m/s",
            delta=f"降级 {accuracy.velocity_degradation:.1f}%"
        )
    
    # 综合降级等级
    st.progress(accuracy.overall_degradation / 100, 
                text=f"综合精度降级: {accuracy.overall_degradation:.1f}%")
    
    # 雷达图展示各项精度
    categories = ['测角精度', '测距精度', '测速精度']
    values = [
        100 - accuracy.angle_degradation,
        100 - accuracy.range_degradation,
        100 - accuracy.velocity_degradation
    ]
    
    fig = go.Figure(data=go.Scatterpolar(
        r=values + [values[0]],
        theta=categories + [categories[0]],
        fill='toself',
        name='剩余精度',
        line_color='green',
        fillcolor='rgba(0, 255, 0, 0.3)'
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=False,
        title="精度保留比例",
        height=350
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
    tabs = st.tabs(["🚫 遮挡分析", "📡 散射分析", "🌊 多普勒分析", "🎯 精度分析"])
    
    with tabs[0]:
        render_blocking_results(result)
    
    with tabs[1]:
        render_scattering_results(result)
    
    with tabs[2]:
        render_doppler_results(result)
    
    with tabs[3]:
        render_accuracy_results(result)


def get_risk_class(risk_level: str) -> str:
    """获取风险等级对应的CSS类"""
    risk_map = {
        "低风险": "risk-low",
        "中等风险": "risk-medium",
        "高风险": "risk-high",
        "极高风险": "risk-critical"
    }
    return risk_map.get(risk_level, "risk-low")


def main():
    """主函数"""
    render_header()
    
    # 侧边栏 - 参数配置
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/wind-turbine.png", width=80)
        
        render_radar_config()
        st.markdown("---")
        render_turbine_config()
        st.markdown("---")
        render_target_config()
    
    # 主区域
    col1, col2 = st.columns([1, 1])
    
    with col1:
        render_map()
    
    with col2:
        render_turbine_list()
    
    # 评估按钮
    render_evaluation_button()
    
    # 评估结果
    render_results()
    
    # 页脚
    st.markdown("---")
    st.markdown(
        "<p style='text-align: center; color: #666;'>"
        "© 2026 风机-雷达干扰评估系统 | Version 0.1 (MVP)</p>",
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
