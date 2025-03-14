"""CLI工具模块，包含CLI命令行接口的辅助函数和类"""

import os
import re
import json
import sys
from threading import Lock
from pathlib import Path
from functools import wraps

from loguru import logger
from .constants import (
    DEFAULT_FILES,
    DEFAULT_PROJECT_CONFIG,
    REQUIRED_FILES,
    PROJECT_NAME_PATTERN,
    INVALID_PROJECT_NAME_CHARS,
    ERROR_MESSAGES,
    COLORS
)
from .managers.project_manager import ProjectManager
from .managers.config_manager import ConfigError
from .managers.image_manager import ImageManager, ImageBuildError
from .managers.container_manager import ContainerManager, ContainerError
from .utils import confirm_action

# 状态检查函数
def check_project_status(project_manager, operation_type):
    """
    检查项目状态并根据操作类型提供警告
    
    Args:
        project_manager: 项目管理器实例
        operation_type: 操作类型，可选值: 'build', 'up', 'down', 'save', 'logs'
        
    Returns:
        bool: 是否可以继续操作
    """
    try:
        status = project_manager.get_status()
        
        # 根据操作类型检查状态
        if operation_type == 'build':
            # 检查是否已有镜像
            try:
                project_manager.docker_client.images.get(status['image']['name'])
                if not confirm_action(f"镜像 {status['image']['name']} 已存在，是否重新构建?"):
                    logger.warning("操作已取消")
                    return False
            except Exception:
                # 镜像不存在，可以继续
                pass
                
        elif operation_type == 'up':
            # 检查容器是否已在运行
            if status['container']['status'] == 'running':
                logger.warning(f"容器 {status['container']['name']} 已在运行中")
                if not confirm_action("是否重新启动容器?"):
                    logger.warning("操作已取消")
                    return False
            
            # 检查镜像是否存在
            try:
                project_manager.docker_client.images.get(status['image']['name'])
            except Exception:
                logger.error(f"镜像 {status['image']['name']} 不存在，请先构建镜像")
                if confirm_action("是否现在构建镜像?"):
                    if not project_manager.image_manager.build_image():
                        logger.error("镜像构建失败，无法启动容器")
                        return False
                else:
                    logger.warning("操作已取消")
                    return False
                
        elif operation_type == 'down':
            # 检查容器是否在运行
            if status['container']['status'] != 'running':
                logger.warning(f"容器 {status['container']['name']} 未在运行中")
                return False
            
            # 确认是否停止容器
            if not confirm_action("确定要停止容器吗?"):
                logger.warning("操作已取消")
                return False
                
        elif operation_type == 'save':
            # 检查容器是否在运行
            if status['container']['status'] != 'running':
                logger.error(f"容器 {status['container']['name']} 未在运行中，无法保存")
                return False
                
        elif operation_type == 'logs':
            # 检查容器是否在运行
            if status['container']['status'] != 'running':
                logger.warning(f"容器 {status['container']['name']} 未在运行中，无法查看日志")
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"检查项目状态失败: {e}")
        return True  # 如果无法检查状态，默认允许操作继续

# 项目上下文管理
class ProjectContext:
    """项目上下文管理类"""
    _instance = None
    _lock = Lock()
    
    def __init__(self):
        self._project_dir = None
        self._project_name = None
        self._project_lock = Lock()
    
    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = cls()
        return cls._instance
    
    @property
    def project_dir(self):
        """获取当前项目目录"""
        if not self._project_dir:
            self._project_dir = os.getcwd()
        return self._project_dir
    
    @project_dir.setter
    def project_dir(self, path):
        """设置当前项目目录"""
        self._project_dir = os.path.abspath(path) if path else os.getcwd()
    
    @property
    def project_name(self):
        """获取当前项目名称"""
        if not self._project_name:
            self._project_name = os.path.basename(self.project_dir)
        return self._project_name
    
    @project_name.setter
    def project_name(self, name):
        """设置当前项目名称"""
        if name:
            self._validate_project_name(name)
            self._project_name = name
    
    @staticmethod
    def _validate_project_name(name):
        """验证项目名称的安全性"""
        if not name:
            raise ValueError(ERROR_MESSAGES['project_name_empty'])
        if not re.match(PROJECT_NAME_PATTERN, name):
            raise ValueError(ERROR_MESSAGES['project_name_invalid'])
        if any(char in name for char in INVALID_PROJECT_NAME_CHARS):
            raise ValueError(ERROR_MESSAGES['project_name_illegal'])

def get_project_manager():
    """获取当前项目的管理器"""
    ctx = ProjectContext.get_instance()
    project_dir = ctx.project_dir
    
    # 尝试从配置文件加载项目信息
    config_file = os.path.join(project_dir, 'config.json')
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 使用配置文件中的项目名称
            project_name = config.get('project', {}).get('name')
            if not project_name:
                project_name = ctx.project_name
            
            # 创建项目管理器并设置配置
            project_manager = ProjectManager(project_name, project_dir, config)
            return project_manager
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            # 继续使用上下文信息创建项目管理器
    
    # 如果无法从配置文件加载，使用上下文信息
    project_manager = ProjectManager(ctx.project_name, project_dir)
    return project_manager

def check_config_exists(func):
    """
    装饰器：检查配置文件是否存在
    
    Args:
        func: 要装饰的函数
        
    Returns:
        装饰后的函数
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # 获取当前项目目录
        ctx = ProjectContext.get_instance()
        project_dir = ctx.project_dir
        
        # 检查配置文件是否存在
        config_file = os.path.join(project_dir, 'config.json')
        if not os.path.exists(config_file):
            logger.error(f"错误：项目配置文件不存在: {config_file}")
            logger.info("请先使用 'dm init' 命令初始化项目，或在包含config.json的目录中运行命令")
            sys.exit(1)
        
        # 调用原函数
        return func(*args, **kwargs)
    
    return wrapper 