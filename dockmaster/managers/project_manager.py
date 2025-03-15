"""项目管理器类"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict, TYPE_CHECKING

from loguru import logger

from ..constants import DefaultProjectConfig
from ..interactive_utils import confirm_action
from .base_manager import BaseManager
from .config_manager import ConfigError, ConfigManager
from .image_manager import ImageManager
from .container_manager import ContainerManager

if TYPE_CHECKING:
    from .scheduler_daemon import SchedulerDaemon


class ProjectOperationError(Exception):
    """项目操作错误"""

    pass


class ProjectStatus(TypedDict):
    """项目状态类型"""
    project: Dict[str, str]
    image: Dict[str, Any]
    container: Dict[str, Any]
    schedule: Dict[str, Any]


class ProjectManager(BaseManager):
    """项目管理器类，用于管理项目配置和资源"""

    project_name: str
    project_dir: str
    config: DefaultProjectConfig
    config_manager: ConfigManager
    image_manager: Optional[ImageManager]
    container_manager: Optional[ContainerManager]

    def __init__(self, project_name: str, project_dir: Optional[str] = None, config: Optional[DefaultProjectConfig] = None) -> None:
        """
        初始化项目管理器

        Args:
            project_name: 项目名称
            project_dir: 项目目录路径，默认为None
            config: 项目配置，默认为None
        """
        super().__init__()
        self.project_name = project_name
        self.project_dir = project_dir or os.getcwd()

        # 初始化配置管理器
        self.config_manager = ConfigManager(project_name, self.project_dir, config)
        self.config = self.config_manager.config

        self.image_manager = None
        self.container_manager = None

        # 如果提供了配置，初始化管理器
        if config:
            self._init_managers()

    def create_project(self, project_dir: str) -> bool:
        """
        创建新项目

        Args:
            project_dir: 项目目录路径

        Returns:
            bool: 是否创建成功
        """
        try:
            # 验证目录
            project_dir = os.path.abspath(project_dir)
            if not os.path.exists(project_dir):
                os.makedirs(project_dir)

            # 更新项目目录
            self.project_dir = project_dir
            self.config_manager.project_dir = project_dir

            # 创建默认配置
            self.config = self.config_manager.create_default_config()

            # 保存配置
            self.config_manager.save_config()

            # 初始化管理器
            self._init_managers()

            # 记录日志但不输出到控制台
            logger.debug(f"项目 '{self.project_name}' 创建成功")
            return True

        except Exception as e:
            logger.error(f"创建项目失败: {e}")
            return False

    def load_project(self) -> bool:
        """
        加载项目配置

        Returns:
            bool: 是否加载成功
        """
        try:
            # 加载配置
            self.config = self.config_manager.load_config()

            # 初始化管理器
            self._init_managers()

            return True

        except Exception as e:
            logger.error(f"加载项目失败: {e}")
            return False

    def update_config(self, config_updates: Dict[str, Any]) -> bool:
        """
        更新项目配置

        Args:
            config_updates: 要更新的配置项

        Returns:
            bool: 是否更新成功
        """
        try:
            # 更新配置
            self.config = self.config_manager.update_config(config_updates)

            # 重新初始化管理器
            self._init_managers()

            return True

        except Exception as e:
            logger.error(f"更新配置失败: {e}")
            return False

    def cleanup_resources(self) -> bool:
        """
        清理项目资源

        Returns:
            bool: 是否清理成功
        """
        try:
            if self.container_manager:
                self.container_manager.cleanup_container()
            return True
        except Exception as e:
            logger.error(f"清理资源失败: {e}")
            return False

    def _init_managers(self) -> None:
        """初始化镜像和容器管理器"""
        image_config = self.config["image"]
        container_config = self.config["container"]

        self.image_manager = ImageManager(
            project_dir=self.project_dir, image_name=image_config["name"]
        )

        self.container_manager = ContainerManager(
            project_dir=self.project_dir, container_name=container_config["name"]
        )

    def get_status(self) -> ProjectStatus:
        """
        获取项目状态

        Returns:
            ProjectStatus: 项目状态信息
        """
        try:
            # 获取容器状态
            container_status = "未运行"
            try:
                container = self.docker_client.containers.get(self.config["container"]["name"])
                container_status = container.status
            except Exception:
                pass

            # 获取定时任务信息
            schedules = []
            if "schedule" in self.config and self.config["schedule"]:
                for task_type, task_info in self.config["schedule"].items():
                    if task_info and "cron" in task_info:
                        schedules.append({"type": task_type, "schedule": task_info["cron"]})

            # 获取镜像摘要信息
            image_summary = self.image_manager.get_images_summary()

            # 检查镜像是否存在
            image_exists = False
            try:
                self.docker_client.images.get(self.image_manager.image_name)
                image_exists = True
            except Exception:
                pass

            # 获取调度器状态
            scheduler_status = self.container_manager.get_scheduler_status()
            tasks = self.container_manager.list_scheduled_tasks()

            # 构建状态信息
            status = {
                "project": {"name": self.project_name, "directory": self.project_dir},
                "image": {
                    "name": self.config["image"]["name"],
                    "registry": {"url": self.config["image"]["registry"]["url"]},
                    "exists": image_exists,
                    "backup_count": len(image_summary["project_images"]),
                    "total_size_mb": sum(img["size_mb"] for img in image_summary["project_images"]),
                    "latest_backup": (
                        image_summary["project_images"][0]["created_ago"]
                        if image_summary["project_images"]
                        else None
                    ),
                    "summary": image_summary,
                },
                "container": {"name": self.config["container"]["name"], "status": container_status},
                "schedules": schedules,
                "scheduler": scheduler_status,
                "tasks": tasks,
            }

            return status

        except Exception as e:
            logger.error(f"获取项目状态失败: {e}")
            raise ProjectOperationError(f"获取项目状态失败: {str(e)}")

    def get_config(self) -> DefaultProjectConfig:
        """
        获取项目配置

        Returns:
            DefaultProjectConfig: 项目配置信息
        """
        return self.config
