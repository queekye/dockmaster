"""CLI工具模块，包含CLI命令行接口的辅助函数和类"""

import json
import os
import re
import sys
from functools import wraps
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional, Callable, TypeVar, cast

from loguru import logger

from .constants import (
    COLORS,
    DEFAULT_FILES,
    DEFAULT_PROJECT_CONFIG,
    ERROR_MESSAGES,
    INVALID_PROJECT_NAME_CHARS,
    PROJECT_NAME_PATTERN,
    REQUIRED_FILES,
)
from .managers.config_manager import ConfigError
from .managers.container_manager import ContainerError, ContainerManager
from .managers.image_manager import ImageBuildError, ImageManager
from .managers.project_manager import ProjectManager
from .utils import confirm_action

F = TypeVar('F', bound=Callable[..., Any])

def check_project_status(project_manager: ProjectManager, operation_type: str) -> bool:
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
        if operation_type == "build":
            # 检查是否已有镜像
            try:
                project_manager.docker_client.images.get(status["image"]["name"])
                if not confirm_action(f"镜像 {status['image']['name']} 已存在，是否重新构建?"):
                    logger.warning("操作已取消")
                    return False
            except Exception:
                # 镜像不存在，可以继续
                pass

        elif operation_type == "up":
            # 检查容器是否已在运行
            if status["container"]["status"] == "running":
                logger.warning(f"容器 {status['container']['name']} 已在运行中")
                if not confirm_action("是否重新启动容器?"):
                    logger.warning("操作已取消")
                    return False
                else:
                    # 设置重启标志
                    project_manager.container_manager._is_restart = True

            # 检查镜像是否存在
            try:
                project_manager.docker_client.images.get(status["image"]["name"])
            except Exception:
                logger.error(f"镜像 {status['image']['name']} 不存在，请先构建镜像")
                if confirm_action("是否现在构建镜像?"):
                    if not project_manager.image_manager.build_image():
                        logger.error("镜像构建失败，无法启动容器")
                        return False
                else:
                    logger.warning("操作已取消")
                    return False

        elif operation_type == "down":
            # 检查容器是否在运行
            if status["container"]["status"] != "running":
                logger.warning(f"容器 {status['container']['name']} 未在运行中")
                return False

            # 确认是否停止容器
            if not confirm_action("确定要停止容器吗?"):
                logger.warning("操作已取消")
                return False

        elif operation_type == "save":
            # 检查容器是否在运行
            if status["container"]["status"] != "running":
                logger.error(f"容器 {status['container']['name']} 未在运行中，无法保存")
                return False

        elif operation_type == "logs":
            # 检查容器是否在运行
            if status["container"]["status"] != "running":
                logger.warning(f"容器 {status['container']['name']} 未在运行中，无法查看日志")
                return False

        return True

    except Exception as e:
        logger.error(f"检查项目状态失败: {e}")
        return True  # 如果无法检查状态，默认允许操作继续


# 项目上下文管理
class ProjectContext:
    """项目上下文管理类"""

    _instance: Optional['ProjectContext'] = None
    _lock: Lock = Lock()
    _project_dir: Optional[str] = None
    _project_name: Optional[str] = None

    def __init__(self) -> None:
        """初始化项目上下文"""
        if ProjectContext._instance is not None:
            raise RuntimeError("ProjectContext是单例类，请使用get_instance()获取实例")
        ProjectContext._instance = self

    @classmethod
    def get_instance(cls) -> 'ProjectContext':
        """获取ProjectContext单例实例"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = ProjectContext()
            return cls._instance

    @property
    def project_dir(self) -> Optional[str]:
        """获取项目目录"""
        if self._project_dir is None:
            self._project_dir = self._find_project_dir()
        return self._project_dir

    def _find_project_dir(self) -> Optional[str]:
        """
        从当前目录开始向上查找包含config.json的目录
        
        Returns:
            Optional[str]: 找到的项目目录路径，如果未找到则返回当前目录
        """
        current = Path.cwd()
        while current != current.parent:
            if (current / "config.json").exists():
                return str(current)
            current = current.parent
        return str(Path.cwd())

    @project_dir.setter
    def project_dir(self, path: Optional[str]) -> None:
        """设置项目目录"""
        self._project_dir = str(Path(path).resolve()) if path else None

    @property
    def project_name(self) -> Optional[str]:
        """获取项目名称"""
        return self._project_name

    @project_name.setter
    def project_name(self, name: Optional[str]) -> None:
        """设置项目名称"""
        if name:
            self._validate_project_name(name)
        self._project_name = name

    @staticmethod
    def _validate_project_name(name: str) -> None:
        """
        验证项目名称是否合法

        Args:
            name: 项目名称

        Raises:
            ValueError: 当项目名称不合法时抛出
        """
        if not name:
            raise ValueError(ERROR_MESSAGES["project_name_empty"])
        if not re.match(PROJECT_NAME_PATTERN, name):
            raise ValueError(ERROR_MESSAGES["project_name_invalid"])
        if any(char in name for char in INVALID_PROJECT_NAME_CHARS):
            raise ValueError(ERROR_MESSAGES["project_name_illegal"])


def get_project_manager() -> ProjectManager:
    """
    获取项目管理器实例

    Returns:
        ProjectManager: 项目管理器实例

    Raises:
        RuntimeError: 当项目上下文未初始化时抛出
    """
    ctx = ProjectContext.get_instance()
    project_dir = ctx.project_dir

    # 尝试从配置文件加载项目信息
    config_file = os.path.join(project_dir, "config.json")
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)

            # 使用配置文件中的项目名称
            project_name = config.get("project", {}).get("name")
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


def check_config_exists(func: F) -> F:
    """
    检查配置文件是否存在的装饰器

    Args:
        func: 被装饰的函数

    Returns:
        Callable: 装饰后的函数
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        # 获取当前项目目录
        ctx = ProjectContext.get_instance()
        project_dir = ctx.project_dir  # 这里会自动查找项目目录

        # 检查配置文件是否存在
        config_file = os.path.join(project_dir, "config.json")
        if not os.path.exists(config_file):
            logger.error(f"错误：项目配置文件不存在: {config_file}")
            logger.info("请先使用 'dm init' 命令初始化项目，或在包含config.json的目录中运行命令")
            sys.exit(1)

        # 调用原函数
        return func(*args, **kwargs)

    return wrapper
