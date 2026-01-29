"""
评估结果模型
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import numpy as np


@dataclass
class BlockingResult:
    """遮挡分析结果"""
    blocking_factor: float = 0.0          # 遮挡因子 (%)
    blocking_duration: float = 0.0        # 遮挡持续时间 (%)
    projection_area: float = 0.0          # 投影面积 (m²)
    beam_area: float = 0.0                # 波束截面积 (m²)
    affected_sectors: List[dict] = field(default_factory=list)
    time_series: List[float] = field(default_factory=list)
    
    def get_risk_level(self) -> str:
        """获取风险等级"""
        if self.blocking_factor < 5:
            return "低风险"
        elif self.blocking_factor < 15:
            return "中等风险"
        elif self.blocking_factor < 30:
            return "高风险"
        else:
            return "极高风险"
    
    def to_dict(self) -> dict:
        return {
            'blocking_factor': self.blocking_factor,
            'blocking_duration': self.blocking_duration,
            'projection_area': self.projection_area,
            'beam_area': self.beam_area,
            'affected_sectors': self.affected_sectors,
            'time_series': self.time_series,
            'risk_level': self.get_risk_level()
        }


@dataclass
class ScatteringResult:
    """散射分析结果"""
    interference_power: float = -200.0    # 干扰功率 (dBm)
    target_power: float = -100.0          # 目标回波功率 (dBm)
    sjr: float = 100.0                    # 信干比 (dB)
    sjr_degradation: float = 0.0          # 信干比恶化 (dB)
    affected_turbines: List[dict] = field(default_factory=list)
    range_profile: List[float] = field(default_factory=list)
    
    def get_risk_level(self) -> str:
        """获取风险等级"""
        if self.sjr > 20:
            return "低风险"
        elif self.sjr > 10:
            return "中等风险"
        elif self.sjr > 5:
            return "高风险"
        else:
            return "极高风险"
    
    def to_dict(self) -> dict:
        return {
            'interference_power': self.interference_power,
            'target_power': self.target_power,
            'sjr': self.sjr,
            'sjr_degradation': self.sjr_degradation,
            'affected_turbines': self.affected_turbines,
            'range_profile': self.range_profile,
            'risk_level': self.get_risk_level()
        }


@dataclass
class DopplerResult:
    """多普勒分析结果"""
    max_doppler_shift: float = 0.0        # 最大多普勒频移 (Hz)
    doppler_bandwidth: float = 0.0        # 多普勒带宽 (Hz)
    affected_filters: List[str] = field(default_factory=list)
    mti_degradation: float = 0.0          # MTI改善因子恶化 (dB)
    spectrum_data: dict = field(default_factory=dict)
    velocity_spread: float = 0.0          # 速度展宽 (m/s)
    
    def get_risk_level(self) -> str:
        """获取风险等级"""
        if self.mti_degradation < 3:
            return "低风险"
        elif self.mti_degradation < 6:
            return "中等风险"
        elif self.mti_degradation < 10:
            return "高风险"
        else:
            return "极高风险"
    
    def to_dict(self) -> dict:
        return {
            'max_doppler_shift': self.max_doppler_shift,
            'doppler_bandwidth': self.doppler_bandwidth,
            'affected_filters': self.affected_filters,
            'mti_degradation': self.mti_degradation,
            'spectrum_data': self.spectrum_data,
            'velocity_spread': self.velocity_spread,
            'risk_level': self.get_risk_level()
        }


@dataclass
class AccuracyResult:
    """精度分析结果"""
    angle_error: float = 0.0              # 测角偏差 (度)
    range_error: float = 0.0              # 测距偏差 (m)
    velocity_error: float = 0.0           # 测速偏差 (m/s)
    angle_degradation: float = 0.0        # 测角精度降级比例 (%)
    range_degradation: float = 0.0        # 测距精度降级比例 (%)
    velocity_degradation: float = 0.0     # 测速精度降级比例 (%)
    overall_degradation: float = 0.0      # 综合降级等级
    
    def get_risk_level(self) -> str:
        """获取风险等级"""
        if self.overall_degradation < 20:
            return "低风险"
        elif self.overall_degradation < 40:
            return "中等风险"
        elif self.overall_degradation < 60:
            return "高风险"
        else:
            return "极高风险"
    
    def to_dict(self) -> dict:
        return {
            'angle_error': self.angle_error,
            'range_error': self.range_error,
            'velocity_error': self.velocity_error,
            'angle_degradation': self.angle_degradation,
            'range_degradation': self.range_degradation,
            'velocity_degradation': self.velocity_degradation,
            'overall_degradation': self.overall_degradation,
            'risk_level': self.get_risk_level()
        }


@dataclass
class EvaluationResult:
    """综合评估结果"""
    
    # 各项评估结果
    blocking: BlockingResult = field(default_factory=BlockingResult)
    scattering: ScatteringResult = field(default_factory=ScatteringResult)
    doppler: DopplerResult = field(default_factory=DopplerResult)
    accuracy: AccuracyResult = field(default_factory=AccuracyResult)
    
    # 评估元信息
    evaluation_time: str = ""
    scene_name: str = ""
    
    def get_overall_risk(self) -> str:
        """获取综合风险等级"""
        risks = [
            self.blocking.get_risk_level(),
            self.scattering.get_risk_level(),
            self.doppler.get_risk_level(),
            self.accuracy.get_risk_level()
        ]
        
        if "极高风险" in risks:
            return "极高风险"
        elif "高风险" in risks:
            return "高风险"
        elif "中等风险" in risks:
            return "中等风险"
        else:
            return "低风险"
    
    def get_risk_score(self) -> float:
        """获取风险评分(0-100)"""
        risk_scores = {
            "低风险": 25,
            "中等风险": 50,
            "高风险": 75,
            "极高风险": 100
        }
        
        scores = [
            risk_scores.get(self.blocking.get_risk_level(), 50),
            risk_scores.get(self.scattering.get_risk_level(), 50),
            risk_scores.get(self.doppler.get_risk_level(), 50),
            risk_scores.get(self.accuracy.get_risk_level(), 50)
        ]
        
        return np.mean(scores)
    
    def get_recommendations(self) -> List[str]:
        """获取评估建议"""
        recommendations = []
        
        # 遮挡建议
        if self.blocking.blocking_factor > 15:
            recommendations.append("遮挡效应显著，建议调整风机布局或雷达位置")
        
        # 散射建议
        if self.scattering.sjr < 10:
            recommendations.append("信干比较低，建议增加雷达发射功率或优化信号处理")
        
        # 多普勒建议
        if self.doppler.mti_degradation > 5:
            recommendations.append("多普勒干扰严重，建议使用自适应MTI滤波器")
        
        # 精度建议
        if self.accuracy.overall_degradation > 40:
            recommendations.append("测量精度降级明显，建议进行干扰对消处理")
        
        if not recommendations:
            recommendations.append("当前配置下干扰影响在可接受范围内")
        
        return recommendations
    
    def to_dict(self) -> dict:
        return {
            'blocking': self.blocking.to_dict(),
            'scattering': self.scattering.to_dict(),
            'doppler': self.doppler.to_dict(),
            'accuracy': self.accuracy.to_dict(),
            'evaluation_time': self.evaluation_time,
            'scene_name': self.scene_name,
            'overall_risk': self.get_overall_risk(),
            'risk_score': self.get_risk_score(),
            'recommendations': self.get_recommendations()
        }
