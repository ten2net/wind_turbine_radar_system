# 风机-雷达干扰评估系统 概要设计说明书

## 文档信息

| 项目 | 内容 |
|------|------|
| 文档编号 | WTR-HLD-001 |
| 版本 | V1.0 |
| 编制日期 | 2026-01-29 |
| 关联文档 | WTR-SRS-001 |

---

## 1. 引言

### 1.1 编写目的

本文档基于需求规格说明书，对风机-雷达干扰评估系统进行高层架构设计，明确系统模块划分、接口定义、数据流转和技术选型。

### 1.2 设计原则

1. **模块化设计**：高内聚、低耦合，便于维护和扩展
2. **分层架构**：表示层、业务逻辑层、数据访问层分离
3. **配置驱动**：通过配置文件支持灵活参数调整
4. **可视化优先**：提供丰富的可视化展示能力

---

## 2. 系统架构

### 2.1 总体架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           表示层 (Presentation)                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │  Streamlit   │  │   Plotly     │  │   Mapbox     │  │   Deck.gl    │ │
│  │   UI组件     │  │   图表组件   │  │   地图组件   │  │   3D组件     │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          业务逻辑层 (Business)                           │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                      场景管理模块 (SceneManager)                  │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐         │  │
│  │  │ 场景创建 │  │ 场景编辑 │  │ 场景保存 │  │ 场景加载 │         │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘         │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                      评估引擎模块 (EvalEngine)                    │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐         │  │
│  │  │ 遮挡分析 │  │ 散射分析 │  │ 绕射分析 │  │ 多普勒   │         │  │
│  │  │ (Block)  │  │(Scatter) │  │(Diffract)│  │ (Doppler)│         │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘         │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐                       │  │
│  │  │ 测角偏差 │  │ 测距偏差 │  │ 测速偏差 │                       │  │
│  │  │(Angle)   │  │ (Range)  │  │(Velocity)│                       │  │
│  │  └──────────┘  └──────────┘  └──────────┘                       │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                      可视化模块 (Visualizer)                      │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐         │  │
│  │  │ 地图渲染 │  │ 3D场景   │  │ 图表绘制 │  │ 热力图   │         │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘         │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                      报告模块 (Reporter)                          │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐                        │  │
│  │  │ PDF导出  │  │ Excel导出│  │ 报告模板 │                        │  │
│  │  └──────────┘  └──────────┘  └──────────┘                        │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           数据层 (Data)                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │  场景配置    │  │  风机型号库  │  │  雷达型号库  │  │  评估结果    │ │
│  │  (JSON)      │  │  (SQLite)    │  │  (SQLite)    │  │  (Memory)    │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 技术栈选型

| 层级 | 技术选型 | 版本 | 用途 |
|------|----------|------|------|
| 前端框架 | Streamlit | 1.28+ | Web应用框架 |
| 地图服务 | Mapbox GL JS | 2.15+ | 2D/3D地图渲染 |
| 图表库 | Plotly | 5.18+ | 交互式图表 |
| 3D可视化 | PyDeck/Deck.gl | 0.8+ | 大规模数据可视化 |
| 数值计算 | NumPy | 1.24+ | 矩阵运算 |
| 数据处理 | Pandas | 2.0+ | 数据处理分析 |
| 科学计算 | SciPy | 1.11+ | 科学计算函数 |
| 数据存储 | SQLite | 3.4+ | 本地数据库 |
| 报告生成 | ReportLab | 4.0+ | PDF生成 |

---

## 3. 模块设计

### 3.1 场景管理模块 (SceneManager)

**职责：** 负责场景的创建、编辑、保存和加载

**类图：**

```
┌─────────────────────────────────────────────────────────┐
│                    SceneManager                         │
├─────────────────────────────────────────────────────────┤
│ - scenes: Dict[str, Scene]                              │
│ - current_scene: Scene                                  │
├─────────────────────────────────────────────────────────┤
│ + create_scene(name: str) -> Scene                      │
│ + load_scene(scene_id: str) -> Scene                    │
│ + save_scene(scene: Scene) -> bool                      │
│ + delete_scene(scene_id: str) -> bool                   │
│ + get_scene_list() -> List[SceneInfo]                   │
│ + import_turbines(file_path: str) -> List[Turbine]      │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                       Scene                             │
├─────────────────────────────────────────────────────────┤
│ - scene_id: str                                         │
│ - name: str                                             │
│ - created_at: datetime                                  │
│ - modified_at: datetime                                 │
│ - radar: RadarConfig                                    │
│ - turbines: List[Turbine]                               │
│ - environment: EnvironmentConfig                        │
├─────────────────────────────────────────────────────────┤
│ + add_turbine(turbine: Turbine)                         │
│ + remove_turbine(turbine_id: str)                       │
│ + update_radar(radar: RadarConfig)                      │
│ + to_dict() -> dict                                     │
│ + from_dict(data: dict) -> Scene                        │
└─────────────────────────────────────────────────────────┘
```

**数据结构：**

```python
@dataclass
class RadarConfig:
    """雷达配置"""
    name: str
    frequency_ghz: float          # 工作频率(GHz)
    power_kw: float               # 发射功率(kW)
    antenna_gain_dbi: float       # 天线增益(dBi)
    beamwidth_deg: float          # 波束宽度(度)
    pulse_width_us: float         # 脉冲宽度(μs)
    prf_hz: float                 # 脉冲重复频率(Hz)
    antenna_height_m: float       # 天线高度(m)
    max_range_km: float           # 最大探测距离(km)
    range_resolution_m: float     # 距离分辨率(m)
    angle_resolution_deg: float   # 角度分辨率(度)
    latitude: float               # 纬度
    longitude: float              # 经度
    altitude_m: float = 0         # 海拔高度(m)

@dataclass
class Turbine:
    """风机配置"""
    turbine_id: str
    name: str
    model: str                    # 型号
    tower_height_m: float         # 塔筒高度(m)
    blade_length_m: float         # 叶片长度(m)
    blade_count: int              # 叶片数量
    rotation_speed_rpm: float     # 转速(rpm)
    tower_diameter_m: float       # 塔筒直径(m)
    rcs_dbsm: float               # RCS(dBm²)
    material: str                 # 材料类型
    latitude: float               # 纬度
    longitude: float              # 经度
    altitude_m: float = 0         # 海拔高度(m)
    yaw_angle_deg: float = 0      # 偏航角(度)

@dataclass
class TargetConfig:
    """目标配置"""
    target_type: str              # 目标类型
    rcs_dbsm: float               # 目标RCS(dBm²)
    altitude_m: float             # 飞行高度(m)
    velocity_ms: float            # 飞行速度(m/s)
```

### 3.2 评估引擎模块 (EvalEngine)

**职责：** 实现各类干扰评估算法的核心计算

**类图：**

```
┌─────────────────────────────────────────────────────────┐
│                      EvalEngine                         │
├─────────────────────────────────────────────────────────┤
│ - radar: RadarConfig                                    │
│ - turbines: List[Turbine]                               │
│ - target: TargetConfig                                  │
├─────────────────────────────────────────────────────────┤
│ + evaluate_all() -> EvaluationResult                    │
│ + evaluate_blocking() -> BlockingResult                 │
│ + evaluate_scattering() -> ScatteringResult             │
│ + evaluate_diffraction() -> DiffractionResult           │
│ + evaluate_doppler() -> DopplerResult                   │
│ + evaluate_accuracy() -> AccuracyResult                 │
└─────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ BlockingModel │   │ScatterModel   │   │DiffractModel  │
├───────────────┤   ├───────────────┤   ├───────────────┤
│+calculate()   │   │+calculate()   │   │+calculate()   │
└───────────────┘   └───────────────┘   └───────────────┘
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ DopplerModel  │   │ AngleModel    │   │  RangeModel   │
├───────────────┤   ├───────────────┤   ├───────────────┤
│+calculate()   │   │+calculate()   │   │+calculate()   │
└───────────────┘   └───────────────┘   └───────────────┘
```

**算法模型接口：**

```python
class BaseModel(ABC):
    """评估模型基类"""
    
    @abstractmethod
    def calculate(self, radar: RadarConfig, 
                  turbines: List[Turbine],
                  target: TargetConfig) -> BaseResult:
        """执行评估计算"""
        pass

class BlockingModel(BaseModel):
    """遮挡模型"""
    
    def calculate(self, radar, turbines, target) -> BlockingResult:
        # 几何光学计算
        # 投影面积计算
        # 遮挡持续时间计算
        pass

class ScatteringModel(BaseModel):
    """散射模型"""
    
    def calculate(self, radar, turbines, target) -> ScatteringResult:
        # 雷达方程计算
        # 信干比计算
        pass

class DiffractionModel(BaseModel):
    """绕射模型"""
    
    def calculate(self, radar, turbines, target) -> DiffractionResult:
        # UTD绕射计算
        # 阴影区分析
        pass

class DopplerModel(BaseModel):
    """多普勒模型"""
    
    def calculate(self, radar, turbines, target) -> DopplerResult:
        # 叶片尖端速度计算
        # 多普勒频移计算
        # 谱宽计算
        pass

class AccuracyModel(BaseModel):
    """精度模型"""
    
    def calculate(self, radar, turbines, target) -> AccuracyResult:
        # 测角偏差计算
        # 测距偏差计算
        # 测速偏差计算
        pass
```

### 3.3 可视化模块 (Visualizer)

**职责：** 负责地图、3D场景和图表的渲染

**类图：**

```
┌─────────────────────────────────────────────────────────┐
│                      Visualizer                         │
├─────────────────────────────────────────────────────────┤
│ - mapbox_token: str                                     │
│ - deck_layers: List[Layer]                              │
├─────────────────────────────────────────────────────────┤
│ + render_map(scene: Scene) -> pydeck.Deck               │
│ + render_3d(scene: Scene, results: Results)             │
│ + render_charts(results: Results) -> List[Figure]       │
│ + render_heatmap(scene: Scene, metric: str)             │
│ + update_layers(scene: Scene)                           │
└─────────────────────────────────────────────────────────┘
```

### 3.4 报告模块 (Reporter)

**职责：** 生成评估报告（PDF/Excel）

```
┌─────────────────────────────────────────────────────────┐
│                       Reporter                          │
├─────────────────────────────────────────────────────────┤
│ - template_path: str                                    │
├─────────────────────────────────────────────────────────┤
│ + generate_pdf(scene: Scene, results: Results)          │
│ + generate_excel(scene: Scene, results: Results)        │
│ + generate_summary(results: Results) -> str             │
└─────────────────────────────────────────────────────────┘
```

---

## 4. 接口设计

### 4.1 模块间接口

| 调用模块 | 被调模块 | 接口函数 | 参数 | 返回值 |
|----------|----------|----------|------|--------|
| UI | SceneManager | create_scene() | name: str | Scene |
| UI | SceneManager | import_turbines() | file_path: str | List[Turbine] |
| UI | EvalEngine | evaluate_all() | scene: Scene | EvaluationResult |
| UI | Visualizer | render_map() | scene: Scene | pydeck.Deck |
| UI | Reporter | generate_pdf() | scene, results | bytes |
| EvalEngine | BlockingModel | calculate() | radar, turbines, target | BlockingResult |
| EvalEngine | ScatteringModel | calculate() | radar, turbines, target | ScatteringResult |

### 4.2 外部接口

**Mapbox API：**
```python
# 地图初始化
map_config = {
    "style": "mapbox://styles/mapbox/satellite-v9",
    "center": [longitude, latitude],
    "zoom": 12,
    "pitch": 45,
    "bearing": 0
}
```

**Plotly图表：**
```python
# 图表配置
fig = go.Figure()
fig.add_trace(go.Scatter(...))
fig.update_layout(...)
```

---

## 5. 数据设计

### 5.1 数据流图

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ 用户输入  │────▶│ 场景管理  │────▶│ 评估引擎  │────▶│ 结果展示  │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
                      │                 │                │
                      ▼                 ▼                ▼
                 ┌──────────┐     ┌──────────┐     ┌──────────┐
                 │ 配置文件  │     │ 型号数据库 │     │ 报告文件  │
                 │ (JSON)   │     │ (SQLite) │     │(PDF/Excel)│
                 └──────────┘     └──────────┘     └──────────┘
```

### 5.2 数据存储设计

**场景配置存储格式：**

```json
{
  "version": "1.0",
  "scenes": [
    {
      "scene_id": "scene_001",
      "name": "近海风电场评估",
      "created_at": "2026-01-29T10:00:00Z",
      "modified_at": "2026-01-29T10:30:00Z",
      "radar": {
        "name": " coastal_radar_01",
        "frequency_ghz": 3.0,
        "power_kw": 100,
        "antenna_gain_dbi": 35,
        "beamwidth_deg": 1.5,
        "pulse_width_us": 1.0,
        "prf_hz": 1000,
        "antenna_height_m": 50,
        "max_range_km": 100,
        "range_resolution_m": 150,
        "angle_resolution_deg": 1.0,
        "latitude": 39.9042,
        "longitude": 116.4074,
        "altitude_m": 10
      },
      "turbines": [
        {
          "turbine_id": "t001",
          "name": "风机001",
          "model": "Vestas V90",
          "tower_height_m": 105,
          "blade_length_m": 45,
          "blade_count": 3,
          "rotation_speed_rpm": 15,
          "tower_diameter_m": 4,
          "rcs_dbsm": 42,
          "material": "金属",
          "latitude": 39.9142,
          "longitude": 116.4174,
          "altitude_m": 5,
          "yaw_angle_deg": 0
        }
      ],
      "target": {
        "target_type": "民航客机",
        "rcs_dbsm": 10,
        "altitude_m": 10000,
        "velocity_ms": 250
      },
      "environment": {
        "temperature_c": 15,
        "humidity_percent": 60,
        "pressure_hpa": 1013,
        "terrain_type": "海上"
      }
    }
  ]
}
```

### 5.3 数据库设计

**风机型号表 (turbine_models)：**

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | INTEGER PRIMARY KEY | 自增ID |
| model_name | VARCHAR(50) | 型号名称 |
| manufacturer | VARCHAR(50) | 制造商 |
| tower_height_m | FLOAT | 塔筒高度 |
| blade_length_m | FLOAT | 叶片长度 |
| blade_count | INTEGER | 叶片数量 |
| rated_power_mw | FLOAT | 额定功率 |
| rcs_dbsm | FLOAT | 雷达散射截面 |
| created_at | TIMESTAMP | 创建时间 |

**雷达型号表 (radar_models)：**

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | INTEGER PRIMARY KEY | 自增ID |
| model_name | VARCHAR(50) | 型号名称 |
| band | VARCHAR(10) | 波段 |
| frequency_ghz | FLOAT | 工作频率 |
| power_kw | FLOAT | 发射功率 |
| antenna_gain_dbi | FLOAT | 天线增益 |
| application | VARCHAR(100) | 用途 |

---

## 6. 部署架构

### 6.1 部署模式

**模式一：本地运行（开发/单机）**
```
┌─────────────────────────────────────┐
│           用户电脑                   │
│  ┌─────────────────────────────┐   │
│  │  Python + Streamlit         │   │
│  │  ┌─────────┐  ┌─────────┐   │   │
│  │  │ 前端UI  │  │后端计算 │   │   │
│  │  └─────────┘  └─────────┘   │   │
│  │  ┌─────────┐  ┌─────────┐   │   │
│  │  │ SQLite  │  │ 本地文件 │   │   │
│  │  └─────────┘  └─────────┘   │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
```

**模式二：服务器部署（多用户）**
```
┌─────────────────────────────────────────────────────────┐
│                    云服务器                              │
│  ┌─────────────────────────────────────────────────┐   │
│  │              Docker Container                    │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────┐  │   │
│  │  │  Streamlit  │  │  Python App │  │  SQLite │  │   │
│  │  │    Server   │  │             │  │         │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────┘  │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────┐
│                   外部服务                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Mapbox API  │  │  CDN静态资源  │  │  可选:Redis  │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 6.2 环境配置

**requirements.txt：**
```
streamlit==1.28.0
plotly==5.18.0
pydeck==0.8.0
numpy==1.24.0
pandas==2.0.0
scipy==1.11.0
reportlab==4.0.0
openpyxl==3.1.0
```

---

## 7. 异常处理设计

### 7.1 异常分类

| 异常类型 | 说明 | 处理策略 |
|----------|------|----------|
| 输入验证异常 | 参数超出有效范围 | 前端校验，提示用户 |
| 计算异常 | 数值计算错误 | 返回默认值，记录日志 |
| 文件异常 | 导入/导出失败 | 友好提示，保留现场 |
| 网络异常 | 地图服务不可用 | 降级显示，缓存数据 |
| 内存异常 | 大规模计算溢出 | 分批处理，限制规模 |

### 7.2 错误码定义

| 错误码 | 说明 | 解决方案 |
|--------|------|----------|
| E001 | 雷达参数无效 | 检查频率、功率等参数范围 |
| E002 | 风机位置重复 | 检查坐标是否冲突 |
| E003 | 文件格式错误 | 使用正确的CSV/Excel模板 |
| E004 | 计算超时 | 减少风机数量或简化模型 |
| E005 | 地图加载失败 | 检查网络连接和Token |

---

## 8. 附录

### 8.1 目录结构

```
wind_turbine_radar_system/
├── docs/                           # 文档目录
│   ├── 01_需求规格说明书_SRS.md
│   ├── 02_概要设计说明书_HLD.md
│   ├── 03_详细设计说明书_DDD.md
│   └── 04_版本迭代计划.md
├── src/                            # 源代码
│   ├── app.py                      # 主应用入口
│   ├── config.py                   # 配置管理
│   ├── models/                     # 数据模型
│   │   ├── __init__.py
│   │   ├── radar.py                # 雷达配置
│   │   ├── turbine.py              # 风机配置
│   │   ├── target.py               # 目标配置
│   │   └── scene.py                # 场景配置
│   ├── engine/                     # 评估引擎
│   │   ├── __init__.py
│   │   ├── base_model.py           # 基类
│   │   ├── blocking.py             # 遮挡模型
│   │   ├── scattering.py           # 散射模型
│   │   ├── diffraction.py          # 绕射模型
│   │   ├── doppler.py              # 多普勒模型
│   │   └── accuracy.py             # 精度模型
│   ├── visualization/              # 可视化
│   │   ├── __init__.py
│   │   ├── map_renderer.py         # 地图渲染
│   │   ├── chart_renderer.py       # 图表渲染
│   │   └── deck_renderer.py        # 3D渲染
│   ├── components/                 # UI组件
│   │   ├── __init__.py
│   │   ├── sidebar.py              # 侧边栏
│   │   ├── map_view.py             # 地图视图
│   │   ├── result_panel.py         # 结果面板
│   │   └── parameter_forms.py      # 参数表单
│   ├── utils/                      # 工具函数
│   │   ├── __init__.py
│   │   ├── geo_utils.py            # 地理计算
│   │   ├── radar_utils.py          # 雷达计算
│   │   └── file_utils.py           # 文件操作
│   └── data/                       # 数据文件
│       ├── turbine_models.db       # 风机型号库
│       └── radar_models.db         # 雷达型号库
├── tests/                          # 测试代码
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_engine.py
│   └── test_visualization.py
├── assets/                         # 静态资源
│   ├── css/
│   └── images/
├── requirements.txt
├── Dockerfile
└── README.md
```

---

**文档结束**
