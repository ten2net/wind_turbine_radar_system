"""
评估引擎主类
"""
from datetime import datetime
from typing import List

from models.radar import RadarConfig
from models.turbine import Turbine
from models.target import TargetConfig
from models.scene import Scene
from models.results import EvaluationResult

from .blocking import BlockingModel
from .scattering import ScatteringModel
from .doppler import DopplerModel
from .accuracy import AccuracyModel


class EvalEngine:
    """评估引擎主类"""
    
    def __init__(self):
        self.blocking_model = BlockingModel()
        self.scattering_model = ScatteringModel()
        self.doppler_model = DopplerModel()
        self.accuracy_model = AccuracyModel(self.scattering_model)
    
    def evaluate(self, scene: Scene) -> EvaluationResult:
        """
        执行完整评估
        
        Args:
            scene: 场景配置
            
        Returns:
            EvaluationResult: 综合评估结果
        """
        radar = scene.radar
        turbines = scene.turbines
        target = scene.target
        
        # 执行各项评估
        blocking_result = self.blocking_model.calculate(radar, turbines, target)
        scattering_result = self.scattering_model.calculate(radar, turbines, target)
        doppler_result = self.doppler_model.calculate(radar, turbines, target)
        accuracy_result = self.accuracy_model.calculate(radar, turbines, target)
        
        return EvaluationResult(
            blocking=blocking_result,
            scattering=scattering_result,
            doppler=doppler_result,
            accuracy=accuracy_result,
            evaluation_time=datetime.now().isoformat(),
            scene_name=scene.name
        )
    
    def evaluate_blocking(self, scene: Scene):
        """仅执行遮挡评估"""
        return self.blocking_model.calculate(scene.radar, scene.turbines, scene.target)
    
    def evaluate_scattering(self, scene: Scene):
        """仅执行散射评估"""
        return self.scattering_model.calculate(scene.radar, scene.turbines, scene.target)
    
    def evaluate_doppler(self, scene: Scene):
        """仅执行多普勒评估"""
        return self.doppler_model.calculate(scene.radar, scene.turbines, scene.target)
    
    def evaluate_accuracy(self, scene: Scene):
        """仅执行精度评估"""
        return self.accuracy_model.calculate(scene.radar, scene.turbines, scene.target)
