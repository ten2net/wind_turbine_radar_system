# 风机-雷达干扰评估系统 详细设计说明书

## 文档信息

| 项目 | 内容 |
|------|------|
| 文档编号 | WTR-DDD-001 |
| 版本 | V1.0 |
| 编制日期 | 2026-01-29 |
| 关联文档 | WTR-SRS-001, WTR-HLD-001 |

---

## 1. 引言

### 1.1 编写目的

本文档对风机-雷达干扰评估系统的核心模块进行详细设计，包括算法实现细节、数据结构、接口定义和关键代码逻辑。

### 1.2 适用范围

本文档适用于系统开发人员进行编码实现和单元测试。

---

## 2. 核心算法详细设计

### 2.1 遮挡分析模型 (BlockingModel)

#### 2.1.1 算法原理

遮挡分析基于几何光学原理，计算风机在雷达视线方向的投影面积与雷达波束截面积的比例。

#### 2.1.2 数学模型

```
1. 雷达-风机视线向量：
   v_los = [x_t - x_r, y_t - y_r, z_t - z_r]

2. 风机投影面积计算：
   塔筒投影：A_tower = d_tower × h_tower × |sin(θ)|
   叶片投影：A_blade = N_blade × L_blade × w_blade × |cos(α)|
   总投影：A_turbine = A_tower + A_blade

3. 雷达波束截面积：
   A_beam = π × (R × tan(θ_3dB/2))²

4. 遮挡因子：
   η = min(A_turbine / A_beam, 1.0) × 100%

5. 遮挡持续时间：
   T_block = (N_blade × θ_blade) / (2π × RPM/60)
   其中 θ_blade = arctan(w_blade / R)
```

#### 2.1.3 详细实现

```python
import numpy as np
from typing import List, Tuple
from dataclasses import dataclass

@dataclass
class BlockingResult:
    """遮挡分析结果"""
    blocking_factor: float          # 遮挡因子 (%)
    blocking_duration: float        # 遮挡持续时间 (%)
    projection_area: float          # 投影面积 (m²)
    beam_area: float                # 波束截面积 (m²)
    affected_sectors: List[dict]    # 受影响扇区
    time_series: List[float]        # 时域遮挡序列

class BlockingModel:
    """遮挡分析模型"""
    
    def __init__(self):
        self.sector_resolution = 1.0  # 扇区分辨率(度)
    
    def calculate(self, radar, turbines, target=None) -> BlockingResult:
        """
        计算遮挡效应
        
        Args:
            radar: 雷达配置
            turbines: 风机列表
            target: 目标配置（可选）
            
        Returns:
            BlockingResult: 遮挡分析结果
        """
        total_blocking = 0.0
        max_blocking = 0.0
        all_sectors = []
        
        for turbine in turbines:
            # 计算雷达-风机距离
            distance = self._calculate_distance(radar, turbine)
            
            # 计算投影面积
            proj_area = self._calculate_projection(radar, turbine, distance)
            
            # 计算波束截面积
            beam_area = self._calculate_beam_area(radar, distance)
            
            # 计算遮挡因子
            blocking = min(proj_area / beam_area, 1.0) * 100
            
            # 计算遮挡持续时间
            duration = self._calculate_blocking_duration(turbine, radar, distance)
            
            # 确定受影响扇区
            sector = self._calculate_affected_sector(radar, turbine)
            
            total_blocking += blocking
            max_blocking = max(max_blocking, blocking)
            all_sectors.append({
                'turbine_id': turbine.turbine_id,
                'blocking': blocking,
                'duration': duration,
                'sector': sector,
                'distance': distance
            })
        
        # 计算时域遮挡序列（一个旋转周期）
        time_series = self._calculate_time_series(turbines, radar)
        
        return BlockingResult(
            blocking_factor=min(total_blocking, 100.0),
            blocking_duration=max_blocking,
            projection_area=proj_area,
            beam_area=beam_area,
            affected_sectors=all_sectors,
            time_series=time_series
        )
    
    def _calculate_distance(self, radar, turbine) -> float:
        """计算雷达-风机距离（米）"""
        # 使用Haversine公式计算水平距离
        R = 6371000  # 地球半径(米)
        lat1, lon1 = np.radians(radar.latitude), np.radians(radar.longitude)
        lat2, lon2 = np.radians(turbine.latitude), np.radians(turbine.longitude)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
        c = 2 * np.arcsin(np.sqrt(a))
        horizontal_distance = R * c
        
        # 计算斜距
        height_diff = (turbine.altitude_m + turbine.tower_height_m) - \
                      (radar.altitude_m + radar.antenna_height_m)
        slant_range = np.sqrt(horizontal_distance**2 + height_diff**2)
        
        return slant_range
    
    def _calculate_projection(self, radar, turbine, distance) -> float:
        """计算风机投影面积"""
        # 计算视线仰角
        height_diff = (turbine.altitude_m + turbine.tower_height_m) - \
                      (radar.altitude_m + radar.antenna_height_m)
        elevation = np.arctan2(height_diff, 
                              np.sqrt(distance**2 - height_diff**2))
        
        # 塔筒投影（视为圆柱体）
        tower_height = turbine.tower_height_m
        tower_diameter = turbine.tower_diameter_m
        tower_proj = tower_height * tower_diameter * np.abs(np.cos(elevation))
        
        # 叶片投影（简化模型：叶片在旋转平面内的投影）
        blade_length = turbine.blade_length_m
        blade_width = blade_length * 0.1  # 假设叶片宽度为长度的10%
        blade_proj = turbine.blade_count * blade_length * blade_width
        
        # 总投影（考虑叶片旋转的平均效果）
        total_proj = tower_proj + blade_proj * 0.5
        
        return total_proj
    
    def _calculate_beam_area(self, radar, distance) -> float:
        """计算雷达波束截面积"""
        # 3dB波束宽度转换为弧度
        beamwidth_rad = np.radians(radar.beamwidth_deg)
        
        # 波束半径
        beam_radius = distance * np.tan(beamwidth_rad / 2)
        
        # 波束截面积
        beam_area = np.pi * beam_radius**2
        
        return beam_area
    
    def _calculate_blocking_duration(self, turbine, radar, distance) -> float:
        """计算遮挡持续时间占比"""
        # 叶片在视线方向的角宽度
        blade_width = turbine.blade_length_m * 0.1
        angular_width = np.arctan(blade_width / distance)
        
        # 旋转周期（秒）
        rotation_period = 60.0 / turbine.rotation_speed_rpm
        
        # 单个叶片遮挡时间
        single_blade_time = angular_width / (2 * np.pi) * rotation_period
        
        # 总遮挡时间（一个周期内）
        total_block_time = turbine.blade_count * single_blade_time
        
        # 遮挡持续时间占比
        duration_ratio = (total_block_time / rotation_period) * 100
        
        return duration_ratio
    
    def _calculate_affected_sector(self, radar, turbine) -> dict:
        """计算受影响扇区"""
        # 计算相对方位角
        delta_lon = turbine.longitude - radar.longitude
        delta_lat = turbine.latitude - radar.latitude
        
        bearing = np.degrees(np.arctan2(delta_lon, delta_lat))
        bearing = (bearing + 360) % 360
        
        # 扇区范围（考虑波束宽度）
        sector_width = radar.beamwidth_deg
        sector_start = (bearing - sector_width / 2) % 360
        sector_end = (bearing + sector_width / 2) % 360
        
        return {
            'center': bearing,
            'start': sector_start,
            'end': sector_end,
            'width': sector_width
        }
    
    def _calculate_time_series(self, turbines, radar, num_points=100) -> List[float]:
        """计算时域遮挡序列"""
        # 模拟一个旋转周期内的遮挡变化
        time_series = []
        rotation_period = 60.0 / max(t.rotation_speed_rpm for t in turbines)
        
        for i in range(num_points):
            t = i / num_points * rotation_period
            blocking = 0.0
            
            for turbine in turbines:
                # 计算当前时刻叶片角度
                angle = 2 * np.pi * t * turbine.rotation_speed_rpm / 60
                
                # 计算投影面积（随角度变化）
                blade_factor = np.abs(np.cos(angle))
                blocking += blade_factor
            
            time_series.append(min(blocking / len(turbines) * 100, 100))
        
        return time_series
```

### 2.2 散射分析模型 (ScatteringModel)

#### 2.2.1 算法原理

基于雷达方程计算风机散射功率，评估对目标检测的信干比影响。

#### 2.2.2 数学模型

```
1. 雷达方程：
   P_r = (P_t × G_t × G_r × λ² × σ) / ((4π)³ × R⁴ × L)

2. 波长计算：
   λ = c / f

3. 风机散射功率：
   P_turbine = (P_t × G_t × G_r × λ² × σ_turbine) / ((4π)³ × R_turbine⁴ × L)

4. 目标回波功率：
   P_target = (P_t × G_t × G_r × λ² × σ_target) / ((4π)³ × R_target⁴ × L)

5. 信干比：
   SJR = P_target / P_turbine (线性)
   SJR_dB = 10 × log₁₀(SJR)

6. 多风机合成干扰：
   P_total = Σ P_turbine_i (非相干叠加)
```

#### 2.2.3 详细实现

```python
@dataclass
class ScatteringResult:
    """散射分析结果"""
    interference_power: float       # 干扰功率 (dBm)
    target_power: float             # 目标回波功率 (dBm)
    sjr: float                      # 信干比 (dB)
    sjr_degradation: float          # 信干比恶化 (dB)
    affected_turbines: List[dict]   # 各风机干扰详情
    range_profile: List[float]      # 距离剖面

class ScatteringModel:
    """散射分析模型"""
    
    # 物理常数
    C = 299792458  # 光速 (m/s)
    K_BOLTZMANN = 1.38e-23  # 玻尔兹曼常数
    T0 = 290  # 标准温度 (K)
    
    def __init__(self, system_loss_db: float = 3.0):
        self.system_loss_db = system_loss_db
        self.system_loss_linear = 10 ** (system_loss_db / 10)
    
    def calculate(self, radar, turbines, target) -> ScatteringResult:
        """
        计算散射干扰
        
        Args:
            radar: 雷达配置
            turbines: 风机列表
            target: 目标配置
            
        Returns:
            ScatteringResult: 散射分析结果
        """
        # 计算波长
        wavelength = self.C / (radar.frequency_ghz * 1e9)
        
        # 计算目标距离（假设目标在雷达最大探测距离处）
        target_distance = target.altitude_m / np.tan(np.radians(3))  # 3度仰角
        
        # 计算目标回波功率
        target_power = self._calculate_radar_return(
            radar, target.rcs_dbsm, target_distance, wavelength
        )
        
        # 计算各风机干扰功率
        turbine_powers = []
        total_interference = 0.0
        
        for turbine in turbines:
            distance = self._calculate_distance(radar, turbine)
            power = self._calculate_radar_return(
                radar, turbine.rcs_dbsm, distance, wavelength
            )
            
            turbine_powers.append({
                'turbine_id': turbine.turbine_id,
                'distance_km': distance / 1000,
                'rcs_dbsm': turbine.rcs_dbsm,
                'power_dbm': power
            })
            
            # 非相干叠加（功率相加）
            total_interference += 10 ** (power / 10)
        
        # 总干扰功率
        interference_dbm = 10 * np.log10(total_interference) if total_interference > 0 else -200
        
        # 计算信干比
        sjr = target_power - interference_dbm
        
        # 计算信干比恶化（假设无干扰时SJR为20dB）
        sjr_degradation = max(0, 20 - sjr)
        
        # 计算距离剖面
        range_profile = self._calculate_range_profile(radar, turbines, wavelength)
        
        return ScatteringResult(
            interference_power=interference_dbm,
            target_power=target_power,
            sjr=sjr,
            sjr_degradation=sjr_degradation,
            affected_turbines=turbine_powers,
            range_profile=range_profile
        )
    
    def _calculate_radar_return(self, radar, rcs_dbsm, distance, wavelength) -> float:
        """计算雷达回波功率 (dBm)"""
        # 雷达方程
        # P_r = P_t * G^2 * λ^2 * σ / ((4π)^3 * R^4 * L)
        
        # 转换为线性单位
        pt_linear = radar.power_kw * 1000  # W
        g_linear = 10 ** (radar.antenna_gain_dbi / 10)
        rcs_linear = 10 ** (rcs_dbsm / 10)
        
        # 计算接收功率
        numerator = pt_linear * (g_linear ** 2) * (wavelength ** 2) * rcs_linear
        denominator = ((4 * np.pi) ** 3) * (distance ** 4) * self.system_loss_linear
        
        pr_linear = numerator / denominator
        
        # 转换为dBm
        pr_dbm = 10 * np.log10(pr_linear * 1000)
        
        return pr_dbm
    
    def _calculate_distance(self, radar, turbine) -> float:
        """计算雷达-风机距离"""
        R = 6371000
        lat1, lon1 = np.radians(radar.latitude), np.radians(radar.longitude)
        lat2, lon2 = np.radians(turbine.latitude), np.radians(turbine.longitude)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
        c = 2 * np.arcsin(np.sqrt(a))
        horizontal_distance = R * c
        
        height_diff = (turbine.altitude_m + turbine.tower_height_m) - \
                      (radar.altitude_m + radar.antenna_height_m)
        slant_range = np.sqrt(horizontal_distance**2 + height_diff**2)
        
        return slant_range
    
    def _calculate_range_profile(self, radar, turbines, wavelength, 
                                  num_points=100) -> List[float]:
        """计算距离剖面干扰"""
        max_range = radar.max_range_km * 1000
        ranges = np.linspace(1000, max_range, num_points)
        profile = []
        
        for r in ranges:
            # 计算该距离处的总干扰
            total_power = 0.0
            for turbine in turbines:
                distance = self._calculate_distance_to_point(radar, turbine, r)
                if abs(distance - r) < radar.range_resolution_m:
                    power = self._calculate_radar_return(
                        radar, turbine.rcs_dbsm, distance, wavelength
                    )
                    total_power += 10 ** (power / 10)
            
            profile_dbm = 10 * np.log10(total_power) if total_power > 0 else -200
            profile.append(profile_dbm)
        
        return profile
    
    def _calculate_distance_to_point(self, radar, turbine, range_distance) -> float:
        """计算风机到雷达视线某点的距离"""
        # 简化计算：假设风机在雷达视线方向上
        turbine_distance = self._calculate_distance(radar, turbine)
        return abs(turbine_distance - range_distance)
```

### 2.3 多普勒分析模型 (DopplerModel)

#### 2.3.1 算法原理

计算旋转叶片产生的多普勒频移和谱宽，评估对动目标检测(MTD)的影响。

#### 2.3.2 数学模型

```
1. 叶片尖端线速度：
   v_tip = 2π × R_blade × RPM / 60

2. 叶片根部线速度：
   v_root = 0

3. 多普勒频移：
   f_d = (2 × v_tip × f₀) / c

4. 多普勒谱宽：
   Δf = (2 × v_tip × f₀) / c  (叶片尖端到根部)

5. 多普勒单元占用：
   N_cells = Δf / f_resolution
   其中 f_resolution = 1 / T_coherent

6. MTI改善因子恶化：
   I_degradation = 10 × log₁₀(1 + P_turbine/P_target)
```

#### 2.3.3 详细实现

```python
@dataclass
class DopplerResult:
    """多普勒分析结果"""
    max_doppler_shift: float        # 最大多普勒频移 (Hz)
    doppler_bandwidth: float        # 多普勒带宽 (Hz)
    affected_filters: List[str]     # 受影响的滤波器
    mti_degradation: float          # MTI改善因子恶化 (dB)
    spectrum_data: dict             # 频谱数据
    velocity_spread: float          # 速度展宽 (m/s)

class DopplerModel:
    """多普勒分析模型"""
    
    C = 299792458  # 光速 (m/s)
    
    def calculate(self, radar, turbines, target) -> DopplerResult:
        """
        计算多普勒效应
        
        Args:
            radar: 雷达配置
            turbines: 风机列表
            target: 目标配置
            
        Returns:
            DopplerResult: 多普勒分析结果
        """
        max_shift = 0.0
        max_bandwidth = 0.0
        max_velocity = 0.0
        
        for turbine in turbines:
            # 计算叶片尖端速度
            tip_velocity = self._calculate_tip_velocity(turbine)
            
            # 计算多普勒频移
            doppler_shift = self._calculate_doppler_shift(
                tip_velocity, radar.frequency_ghz
            )
            
            # 计算多普勒带宽（叶片速度范围）
            doppler_bw = doppler_shift  # 从0到最大值
            
            # 计算速度展宽
            velocity_spread = tip_velocity
            
            max_shift = max(max_shift, doppler_shift)
            max_bandwidth = max(max_bandwidth, doppler_bw)
            max_velocity = max(max_velocity, velocity_spread)
        
        # 确定受影响的滤波器
        affected_filters = self._determine_affected_filters(
            max_shift, max_bandwidth, radar
        )
        
        # 计算MTI改善因子恶化
        mti_deg = self._calculate_mti_degradation(radar, turbines)
        
        # 生成频谱数据
        spectrum = self._generate_spectrum(radar, turbines)
        
        return DopplerResult(
            max_doppler_shift=max_shift,
            doppler_bandwidth=max_bandwidth,
            affected_filters=affected_filters,
            mti_degradation=mti_deg,
            spectrum_data=spectrum,
            velocity_spread=max_velocity
        )
    
    def _calculate_tip_velocity(self, turbine) -> float:
        """计算叶片尖端线速度 (m/s)"""
        # v = ω × r = 2π × n × r / 60
        angular_velocity = 2 * np.pi * turbine.rotation_speed_rpm / 60
        tip_velocity = angular_velocity * turbine.blade_length_m
        return tip_velocity
    
    def _calculate_doppler_shift(self, velocity, frequency_ghz) -> float:
        """计算多普勒频移 (Hz)"""
        # f_d = 2 × v × f₀ / c
        frequency_hz = frequency_ghz * 1e9
        doppler_shift = 2 * velocity * frequency_hz / self.C
        return doppler_shift
    
    def _determine_affected_filters(self, max_shift, bandwidth, radar) -> List[str]:
        """确定受影响的滤波器类型"""
        affected = []
        
        # 计算多普勒滤波器组参数
        prf = radar.prf_hz
        doppler_resolution = prf  # 简化模型
        
        # 判断影响的滤波器
        if bandwidth > doppler_resolution * 0.1:
            affected.append("MTI滤波器")
        
        if max_shift > prf / 2:
            affected.append("距离模糊滤波器")
        
        if bandwidth > prf * 0.5:
            affected.append("所有多普勒滤波器")
        
        if not affected:
            affected.append("无明显影响")
        
        return affected
    
    def _calculate_mti_degradation(self, radar, turbines) -> float:
        """计算MTI改善因子恶化"""
        # 简化模型：假设干扰功率与目标功率比
        # 实际应根据散射模型计算
        assumed_sjr = 10  # dB
        degradation = max(0, 20 - assumed_sjr)  # 假设理想MTI改善因子为20dB
        return degradation
    
    def _generate_spectrum(self, radar, turbines, num_points=200) -> dict:
        """生成多普勒频谱"""
        prf = radar.prf_hz
        frequencies = np.linspace(-prf/2, prf/2, num_points)
        spectrum = np.zeros(num_points)
        
        for turbine in turbines:
            tip_velocity = self._calculate_tip_velocity(turbine)
            max_shift = self._calculate_doppler_shift(tip_velocity, radar.frequency_ghz)
            
            # 生成叶片微多普勒特征（简化模型）
            for i, f in enumerate(frequencies):
                if abs(f) <= max_shift:
                    # 叶片旋转产生的频谱特征
                    spectrum[i] += np.exp(-(f**2) / (2 * (max_shift/3)**2))
        
        # 归一化
        if np.max(spectrum) > 0:
            spectrum = spectrum / np.max(spectrum)
        
        return {
            'frequencies': frequencies.tolist(),
            'amplitude': spectrum.tolist(),
            'prf': prf
        }
```

### 2.4 精度偏差模型 (AccuracyModel)

#### 2.4.1 算法原理

分析风机散射干扰对雷达测角、测距、测速精度的影响。

#### 2.4.2 数学模型

```
1. 测角偏差：
   Δθ = θ_3dB × √(P_turbine / P_target) × sin(φ)
   其中 φ 为干扰信号与目标信号的相位差

2. 测距偏差（多径效应）：
   ΔR = (c × Δτ) / 2
   Δτ = (R_direct - R_multipath) / c
   R_multipath = R_radar_turbine + R_turbine_target

3. 测速偏差：
   Δv = (λ × Δf_d) / 2
   Δf_d 为多普勒频移误差

4. 综合精度降级：
   Degradation = √(Δθ²/θ_resolution² + ΔR²/R_resolution² + Δv²/v_resolution²)
```

#### 2.4.3 详细实现

```python
@dataclass
class AccuracyResult:
    """精度分析结果"""
    angle_error: float              # 测角偏差 (度)
    range_error: float              # 测距偏差 (m)
    velocity_error: float           # 测速偏差 (m/s)
    angle_degradation: float        # 测角精度降级比例 (%)
    range_degradation: float        # 测距精度降级比例 (%)
    velocity_degradation: float     # 测速精度降级比例 (%)
    overall_degradation: float      # 综合降级等级

class AccuracyModel:
    """精度分析模型"""
    
    C = 299792458  # 光速 (m/s)
    
    def __init__(self, scattering_model: ScatteringModel = None):
        self.scattering_model = scattering_model or ScatteringModel()
    
    def calculate(self, radar, turbines, target) -> AccuracyResult:
        """
        计算精度偏差
        
        Args:
            radar: 雷达配置
            turbines: 风机列表
            target: 目标配置
            
        Returns:
            AccuracyResult: 精度分析结果
        """
        # 获取散射干扰数据
        scattering = self.scattering_model.calculate(radar, turbines, target)
        
        # 计算测角偏差
        angle_err = self._calculate_angle_error(radar, scattering)
        
        # 计算测距偏差
        range_err = self._calculate_range_error(radar, turbines, target)
        
        # 计算测速偏差
        velocity_err = self._calculate_velocity_error(radar, turbines, target)
        
        # 计算精度降级比例
        angle_deg = (angle_err / radar.angle_resolution_deg) * 100
        range_deg = (range_err / radar.range_resolution_m) * 100
        
        # 速度分辨率（简化）
        wavelength = self.C / (radar.frequency_ghz * 1e9)
        velocity_resolution = (wavelength * radar.prf_hz) / (2 * 100)  # 假设100个多普勒滤波器
        velocity_deg = (velocity_err / velocity_resolution) * 100 if velocity_resolution > 0 else 0
        
        # 综合降级等级
        overall = np.sqrt(angle_deg**2 + range_deg**2 + velocity_deg**2) / np.sqrt(3)
        
        return AccuracyResult(
            angle_error=angle_err,
            range_error=range_err,
            velocity_error=velocity_err,
            angle_degradation=min(angle_deg, 100),
            range_degradation=min(range_deg, 100),
            velocity_degradation=min(velocity_deg, 100),
            overall_degradation=min(overall, 100)
        )
    
    def _calculate_angle_error(self, radar, scattering) -> float:
        """计算测角偏差"""
        # Δθ = θ_3dB × √(P_turbine / P_target)
        sjr_linear = 10 ** (scattering.sjr / 10)
        interference_ratio = 1 / sjr_linear if sjr_linear > 0 else 0
        
        angle_error = radar.beamwidth_deg * np.sqrt(interference_ratio)
        
        # 添加随机相位影响（简化）
        angle_error *= (1 + 0.3 * np.random.random())
        
        return angle_error
    
    def _calculate_range_error(self, radar, turbines, target) -> float:
        """计算测距偏差（多径效应）"""
        max_error = 0.0
        
        for turbine in turbines:
            # 计算多径距离
            distance_rt = self._calculate_distance(radar, turbine)
            
            # 简化：假设目标在雷达-风机延长线上
            # 多径距离 = 雷达-风机距离 + 风机-目标距离
            distance_tt = 50000  # 假设目标距离50km
            multipath_distance = distance_rt + distance_tt
            
            # 直达距离
            direct_distance = distance_rt + distance_tt  # 简化
            
            # 距离差
            delta_r = abs(multipath_distance - direct_distance)
            
            # 转换为时延误差
            delta_tau = delta_r / self.C
            
            # 距离测量误差（简化模型）
            range_error = (self.C * delta_tau) / 2
            
            max_error = max(max_error, range_error)
        
        return min(max_error, radar.range_resolution_m * 2)
    
    def _calculate_velocity_error(self, radar, turbines, target) -> float:
        """计算测速偏差"""
        # 基于多普勒频移误差
        doppler_model = DopplerModel()
        doppler = doppler_model.calculate(radar, turbines, target)
        
        wavelength = self.C / (radar.frequency_ghz * 1e9)
        
        # 速度误差 = 多普勒误差 × 波长 / 2
        velocity_error = (doppler.doppler_bandwidth * wavelength) / 2
        
        return velocity_error
    
    def _calculate_distance(self, radar, turbine) -> float:
        """计算雷达-风机距离"""
        R = 6371000
        lat1, lon1 = np.radians(radar.latitude), np.radians(radar.longitude)
        lat2, lon2 = np.radians(turbine.latitude), np.radians(turbine.longitude)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
        c = 2 * np.arcsin(np.sqrt(a))
        horizontal_distance = R * c
        
        height_diff = (turbine.altitude_m + turbine.tower_height_m) - \
                      (radar.altitude_m + radar.antenna_height_m)
        slant_range = np.sqrt(horizontal_distance**2 + height_diff**2)
        
        return slant_range
```

---

## 3. 用户界面详细设计

### 3.1 页面布局

```
┌─────────────────────────────────────────────────────────────────────────┐
│  标题栏                                                    [帮助][关于]  │
├──────────────────┬──────────────────────────────────────────────────────┤
│                  │                                                      │
│  ┌────────────┐  │  ┌────────────────────────────────────────────────┐  │
│  │ 雷达参数   │  │  │                                                │  │
│  │ ┌────────┐ │  │  │           Mapbox 地图视图                      │  │
│  │ │频率(GHz)│ │  │  │                                                │  │
│  │ │功率(kW) │ │  │  │    [雷达站标记]        [风机标记]              │  │
│  │ │增益(dBi)│ │  │  │                                                │  │
│  │ │波束宽度 │ │  │  │   点击地图添加风机                               │  │
│  │ │...     │ │  │  │                                                │  │
│  │ └────────┘ │  │  └────────────────────────────────────────────────┘  │
│  ├────────────┤  │                                                      │
│  │ 风机参数   │  │  ┌────────────────────────────────────────────────┐  │
│  │ ┌────────┐ │  │  │  评估结果                                        │  │
│  │ │型号选择│ │  │  │  ┌──────────┬──────────┬──────────┬──────────┐  │  │
│  │ │塔筒高度│ │  │  │  │ 遮挡分析 │ 散射分析 │ 多普勒   │ 精度分析 │  │  │
│  │ │叶片长度│ │  │  │  └──────────┴──────────┴──────────┴──────────┘  │  │
│  │ │转速    │ │  │  │                                                  │  │
│  │ │RCS     │ │  │  │  [图表/表格/3D视图切换]                          │  │
│  │ └────────┘ │  │  │                                                  │  │
│  ├────────────┤  │  │  ┌────────────────────────────────────────────┐  │  │
│  │ 目标参数   │  │  │  │                                            │  │  │
│  │ ┌────────┐ │  │  │  │         Plotly 图表区域                     │  │  │
│  │ │目标类型│ │  │  │  │                                            │  │  │
│  │ │RCS     │ │  │  │  │  [折线图/柱状图/热力图/极坐标图]            │  │  │
│  │ │高度    │ │  │  │  │                                            │  │  │
│  │ │速度    │ │  │  │  └────────────────────────────────────────────┘  │  │
│  │ └────────┘ │  │  │                                                  │  │
│  ├────────────┤  │  └────────────────────────────────────────────────┘  │
│  │ 操作按钮   │  │                                                      │
│  │            │  │                                                      │
│  │ [导入风机] │  │                                                      │
│  │ [清空场景] │  │                                                      │
│  │            │  │                                                      │
│  │ [开始评估] │  │                                                      │
│  │ [导出报告] │  │                                                      │
│  └────────────┘  │                                                      │
│                  │                                                      │
└──────────────────┴──────────────────────────────────────────────────────┘
```

### 3.2 组件详细说明

#### 3.2.1 参数配置面板

```python
import streamlit as st

def render_radar_config():
    """渲染雷达参数配置"""
    st.subheader("雷达参数")
    
    with st.expander("基本参数", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            frequency = st.number_input(
                "工作频率 (GHz)",
                min_value=0.1, max_value=100.0, value=3.0, step=0.1
            )
            power = st.number_input(
                "发射功率 (kW)",
                min_value=1.0, max_value=1000.0, value=100.0, step=10.0
            )
            antenna_gain = st.number_input(
                "天线增益 (dBi)",
                min_value=0.0, max_value=60.0, value=35.0, step=1.0
            )
        
        with col2:
            beamwidth = st.number_input(
                "波束宽度 (度)",
                min_value=0.1, max_value=10.0, value=1.5, step=0.1
            )
            antenna_height = st.number_input(
                "天线高度 (m)",
                min_value=0.0, max_value=500.0, value=50.0, step=5.0
            )
            max_range = st.number_input(
                "最大探测距离 (km)",
                min_value=10.0, max_value=500.0, value=100.0, step=10.0
            )
    
    return {
        'frequency_ghz': frequency,
        'power_kw': power,
        'antenna_gain_dbi': antenna_gain,
        'beamwidth_deg': beamwidth,
        'antenna_height_m': antenna_height,
        'max_range_km': max_range
    }

def render_turbine_config():
    """渲染风机参数配置"""
    st.subheader("风机参数")
    
    # 预设型号选择
    models = {
        "自定义": {},
        "Vestas V90": {"tower": 105, "blade": 45, "rcs": 42},
        "GE Haliade-X": {"tower": 150, "blade": 107, "rcs": 48},
        "金风GW155": {"tower": 100, "blade": 77, "rcs": 45}
    }
    
    selected_model = st.selectbox("选择型号", list(models.keys()))
    
    with st.expander("详细参数", expanded=True):
        defaults = models[selected_model]
        
        tower_height = st.number_input(
            "塔筒高度 (m)",
            min_value=20.0, max_value=200.0,
            value=defaults.get("tower", 80.0), step=5.0
        )
        blade_length = st.number_input(
            "叶片长度 (m)",
            min_value=10.0, max_value=100.0,
            value=defaults.get("blade", 50.0), step=5.0
        )
        rotation_speed = st.number_input(
            "旋转速度 (rpm)",
            min_value=5.0, max_value=30.0, value=15.0, step=1.0
        )
        rcs = st.number_input(
            "RCS (dBm²)",
            min_value=10.0, max_value=60.0,
            value=defaults.get("rcs", 40.0), step=1.0
        )
    
    return {
        'model': selected_model,
        'tower_height_m': tower_height,
        'blade_length_m': blade_length,
        'rotation_speed_rpm': rotation_speed,
        'rcs_dbsm': rcs,
        'blade_count': 3,
        'tower_diameter_m': 4.0
    }
```

#### 3.2.2 地图视图组件

```python
import pydeck as pdk
import pandas as pd

def render_map(radar, turbines, selected_turbine=None):
    """渲染Mapbox地图"""
    
    # 准备雷达数据
    radar_data = pd.DataFrame([{
        'lat': radar.latitude,
        'lon': radar.longitude,
        'name': '雷达站',
        'type': 'radar'
    }])
    
    # 准备风机数据
    turbine_data = pd.DataFrame([
        {
            'lat': t.latitude,
            'lon': t.longitude,
            'name': t.name,
            'type': 'turbine',
            'height': t.tower_height_m
        }
        for t in turbines
    ])
    
    # 合并数据
    all_data = pd.concat([radar_data, turbine_data], ignore_index=True)
    
    # 创建图层
    layers = []
    
    # 雷达站图层（红色大圆点）
    radar_layer = pdk.Layer(
        "ScatterplotLayer",
        radar_data,
        get_position=['lon', 'lat'],
        get_color=[255, 0, 0, 200],
        get_radius=500,
        pickable=True,
        opacity=0.8
    )
    layers.append(radar_layer)
    
    # 风机图层（蓝色圆点，大小与高度相关）
    if len(turbine_data) > 0:
        turbine_layer = pdk.Layer(
            "ScatterplotLayer",
            turbine_data,
            get_position=['lon', 'lat'],
            get_color=[0, 100, 255, 200],
            get_radius=300,
            pickable=True,
            opacity=0.6
        )
        layers.append(turbine_layer)
        
        # 风机高度3D柱状图
        column_layer = pdk.Layer(
            "ColumnLayer",
            turbine_data,
            get_position=['lon', 'lat'],
            get_elevation='height',
            elevation_scale=1,
            radius=200,
            get_fill_color=[0, 150, 255, 180],
            pickable=True,
            auto_highlight=True
        )
        layers.append(column_layer)
    
    # 创建视图
    view_state = pdk.ViewState(
        latitude=radar.latitude,
        longitude=radar.longitude,
        zoom=11,
        pitch=45,
        bearing=0
    )
    
    # 渲染地图
    deck = pdk.Deck(
        layers=layers,
        initial_view_state=view_state,
        tooltip={
            'html': '<b>{name}</b><br/>类型: {type}',
            'style': {'backgroundColor': 'steelblue', 'color': 'white'}
        },
        map_style='mapbox://styles/mapbox/satellite-v9'
    )
    
    return deck
```

#### 3.2.3 结果展示组件

```python
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def render_blocking_results(result):
    """渲染遮挡分析结果"""
    st.subheader("遮挡分析结果")
    
    # 指标卡片
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="遮挡因子",
            value=f"{result.blocking_factor:.1f}%",
            delta="严重" if result.blocking_factor > 20 else "轻微"
        )
    
    with col2:
        st.metric(
            label="遮挡持续时间",
            value=f"{result.blocking_duration:.1f}%"
        )
    
    with col3:
        st.metric(
            label="受影响风机数",
            value=len(result.affected_sectors)
        )
    
    # 时域遮挡图
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=list(range(len(result.time_series))),
        y=result.time_series,
        mode='lines',
        name='遮挡比例',
        line=dict(color='red', width=2)
    ))
    fig.update_layout(
        title="一个旋转周期内的遮挡变化",
        xaxis_title="时间采样点",
        yaxis_title="遮挡比例 (%)",
        height=300
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # 受影响扇区表格
    if result.affected_sectors:
        st.subheader("受影响扇区详情")
        sector_df = pd.DataFrame(result.affected_sectors)
        st.dataframe(sector_df, use_container_width=True)

def render_scattering_results(result):
    """渲染散射分析结果"""
    st.subheader("散射分析结果")
    
    # 指标卡片
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="干扰功率",
            value=f"{result.interference_power:.1f} dBm"
        )
    
    with col2:
        st.metric(
            label="目标回波功率",
            value=f"{result.target_power:.1f} dBm"
        )
    
    with col3:
        st.metric(
            label="信干比",
            value=f"{result.sjr:.1f} dB",
            delta=f"恶化 {result.sjr_degradation:.1f} dB" if result.sjr_degradation > 0 else "正常"
        )
    
    # 距离剖面图
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=list(range(len(result.range_profile))),
        y=result.range_profile,
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
    if result.affected_turbines:
        st.subheader("各风机干扰详情")
        turbine_df = pd.DataFrame(result.affected_turbines)
        st.dataframe(turbine_df, use_container_width=True)

def render_doppler_results(result):
    """渲染多普勒分析结果"""
    st.subheader("多普勒分析结果")
    
    # 指标卡片
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="最大多普勒频移",
            value=f"{result.max_doppler_shift:.0f} Hz"
        )
    
    with col2:
        st.metric(
            label="多普勒带宽",
            value=f"{result.doppler_bandwidth:.0f} Hz"
        )
    
    with col3:
        st.metric(
            label="速度展宽",
            value=f"{result.velocity_spread:.1f} m/s"
        )
    
    # 受影响的滤波器
    st.info(f"受影响的滤波器: {', '.join(result.affected_filters)}")
    
    # 多普勒频谱图
    if result.spectrum_data:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=result.spectrum_data['frequencies'],
            y=result.spectrum_data['amplitude'],
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
    st.subheader("精度分析结果")
    
    # 指标卡片
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="测角偏差",
            value=f"{result.angle_error:.2f}°",
            delta=f"降级 {result.angle_degradation:.1f}%"
        )
    
    with col2:
        st.metric(
            label="测距偏差",
            value=f"{result.range_error:.0f} m",
            delta=f"降级 {result.range_degradation:.1f}%"
        )
    
    with col3:
        st.metric(
            label="测速偏差",
            value=f"{result.velocity_error:.1f} m/s",
            delta=f"降级 {result.velocity_degradation:.1f}%"
        )
    
    # 综合降级等级
    st.progress(result.overall_degradation / 100, 
                text=f"综合精度降级: {result.overall_degradation:.1f}%")
    
    # 雷达图展示各项精度
    categories = ['测角精度', '测距精度', '测速精度']
    values = [
        100 - result.angle_degradation,
        100 - result.range_degradation,
        100 - result.velocity_degradation
    ]
    
    fig = go.Figure(data=go.Scatterpolar(
        r=values + [values[0]],
        theta=categories + [categories[0]],
        fill='toself',
        name='剩余精度'
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=False,
        title="精度保留比例",
        height=350
    )
    st.plotly_chart(fig, use_container_width=True)
```

---

## 4. 关键算法流程图

### 4.1 评估引擎主流程

```
┌─────────────────┐
│   开始评估      │
└────────┬────────┘
         ▼
┌─────────────────┐
│  加载场景配置   │
│  - 雷达参数     │
│  - 风机列表     │
│  - 目标参数     │
└────────┬────────┘
         ▼
┌─────────────────┐     ┌─────────────────┐
│  初始化评估引擎  │────▶│  创建评估模型   │
└────────┬────────┘     │  - 遮挡模型     │
         │              │  - 散射模型     │
         │              │  - 多普勒模型   │
         │              │  - 精度模型     │
         │              └─────────────────┘
         ▼
┌─────────────────┐
│  并行执行评估   │
│  ┌───────────┐  │
│  │遮挡分析   │  │
│  └───────────┘  │
│  ┌───────────┐  │
│  │散射分析   │  │
│  └───────────┘  │
│  ┌───────────┐  │
│  │多普勒分析 │  │
│  └───────────┘  │
│  ┌───────────┐  │
│  │精度分析   │  │
│  └───────────┘  │
└────────┬────────┘
         ▼
┌─────────────────┐
│  汇总评估结果   │
│  - 风险等级判定 │
│  - 建议生成     │
└────────┬────────┘
         ▼
┌─────────────────┐
│  输出评估报告   │
└─────────────────┘
```

### 4.2 遮挡分析详细流程

```
┌─────────────────┐
│  开始遮挡分析   │
└────────┬────────┘
         ▼
┌─────────────────┐
│ 遍历每个风机    │
└────────┬────────┘
         ▼
┌─────────────────┐
│ 计算雷达-风机   │
│ 距离和方位      │
└────────┬────────┘
         ▼
┌─────────────────┐
│ 计算风机投影    │
│ 面积            │
│ - 塔筒投影      │
│ - 叶片投影      │
└────────┬────────┘
         ▼
┌─────────────────┐
│ 计算雷达波束    │
│ 截面积          │
└────────┬────────┘
         ▼
┌─────────────────┐
│ 计算遮挡因子    │
│ = 投影面积/     │
│   波束面积      │
└────────┬────────┘
         ▼
┌─────────────────┐
│ 计算遮挡持续    │
│ 时间            │
└────────┬────────┘
         ▼
┌─────────────────┐
│ 确定受影响      │
│ 扇区            │
└────────┬────────┘
         ▼
┌─────────────────┐
│ 生成时域遮挡    │
│ 序列            │
└────────┬────────┘
         ▼
┌─────────────────┐
│ 汇总所有风机    │
│ 结果            │
└────────┬────────┘
         ▼
┌─────────────────┐
│ 返回遮挡分析    │
│ 结果            │
└─────────────────┘
```

---

## 5. 测试设计

### 5.1 单元测试用例

| 测试模块 | 测试用例 | 输入 | 预期输出 | 测试方法 |
|----------|----------|------|----------|----------|
| BlockingModel | 单风机遮挡 | 雷达+1台风机 | 遮挡因子>0 | 断言验证 |
| BlockingModel | 多风机遮挡 | 雷达+10台风机 | 总遮挡<100% | 边界检查 |
| ScatteringModel | 信干比计算 | 雷达+风机+目标 | SJR>0 | 数值验证 |
| DopplerModel | 多普勒频移 | X波段+15rpm风机 | f_d≈1250Hz | 理论对比 |
| AccuracyModel | 测角偏差 | 已知SJR | Δθ<波束宽度 | 范围验证 |

### 5.2 集成测试场景

| 场景编号 | 场景描述 | 测试重点 |
|----------|----------|----------|
| ITS-001 | 单风机近距离评估 | 遮挡主导效应 |
| ITS-002 | 多风机风电场评估 | 散射叠加效应 |
| ITS-003 | 不同波段雷达对比 | 频率敏感性 |
| ITS-004 | 大规模风电场(100+) | 性能测试 |
| ITS-005 | 边界条件测试 | 极端参数验证 |

---

**文档结束**
