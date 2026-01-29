"""
文件操作工具函数
"""
import json
import os
from pathlib import Path

from models.scene import Scene


def save_scene_to_file(scene: Scene, filepath: str) -> bool:
    """
    保存场景到文件
    
    Args:
        scene: 场景对象
        filepath: 文件路径
        
    Returns:
        是否成功
    """
    try:
        # 确保目录存在
        directory = os.path.dirname(filepath)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
        
        scene.save_to_file(filepath)
        return True
    except Exception as e:
        print(f"保存场景失败: {e}")
        return False


def load_scene_from_file(filepath: str) -> Scene:
    """
    从文件加载场景
    
    Args:
        filepath: 文件路径
        
    Returns:
        场景对象
    """
    try:
        return Scene.load_from_file(filepath)
    except Exception as e:
        print(f"加载场景失败: {e}")
        return Scene()


def get_scenes_directory() -> str:
    """获取场景存储目录"""
    scenes_dir = Path.home() / ".wind_turbine_radar" / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)
    return str(scenes_dir)


def list_saved_scenes() -> list:
    """列出已保存的场景"""
    scenes_dir = get_scenes_directory()
    scenes = []
    
    try:
        for filename in os.listdir(scenes_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(scenes_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        scenes.append({
                            'scene_id': data.get('scene_id', ''),
                            'name': data.get('name', '未命名'),
                            'modified_at': data.get('modified_at', ''),
                            'filepath': filepath
                        })
                except:
                    pass
    except:
        pass
    
    return scenes
