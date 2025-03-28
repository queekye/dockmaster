"""容器管理器类"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union, TypedDict, Literal

import docker
import schedule
import typer
from docker.errors import APIError, NotFound
from docker.models.containers import Container
from loguru import logger
from requests.exceptions import RequestException

from ..constants import COLORS, DEFAULT_FILES, ERROR_MESSAGES
from ..interactive_utils import confirm_action
from ..time_utils import get_timestamp
from ..utils import run_command
from .base_manager import BaseManager
from .image_manager import ImageManager
from .container_monitor import ContainerMonitor
from .scheduler_manager import SchedulerManager


class ContainerError(Exception):
    """容器操作错误"""

    pass


class ScheduleConfig(TypedDict, total=False):
    """定时任务配置类型"""
    cron: str
    interval: int
    unit: Literal['minutes', 'hours', 'days', 'weeks']
    at: str


class SchedulerStatus(TypedDict):
    """调度器状态类型"""
    running: bool
    pid: Optional[int]
    start_time: Optional[str]
    tasks: Dict[str, Any]


class ContainerManager(BaseManager):
    """容器管理器类，用于管理容器的生命周期和维护"""

    MAX_RETRIES: int = 3
    RETRY_DELAY: int = 2
    STARTUP_TIMEOUT: int = 30

    project_dir: Path
    container_name: str
    compose_file: Optional[Path]
    _is_restart: bool

    def __init__(self, project_dir: str, container_name: str) -> None:
        """
        初始化容器管理器

        Args:
            project_dir: 项目目录路径
            container_name: 容器名称
        """
        super().__init__()
        self.project_dir = Path(project_dir)
        self.container_name = container_name
        self.compose_file = None
        self._is_restart = False
        self._check_docker_connection()
        
        # 初始化辅助管理器
        self.scheduler_manager = SchedulerManager(project_dir, container_name)
        self.monitor = ContainerMonitor(project_dir, container_name)

    def _check_docker_connection(self) -> None:
        """检查Docker守护进程连接"""
        try:
            self.docker_client.ping()
        except (APIError, RequestException) as e:
            raise ContainerError(f"无法连接到Docker守护进程: {str(e)}")

    def _wait_for_container_status(
        self, expected_status: str, timeout: Optional[int] = None
    ) -> Tuple[bool, Optional[str]]:
        """等待容器达到预期状态"""
        if not timeout:
            timeout = self.STARTUP_TIMEOUT

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                container = self.docker_client.containers.get(self.container_name)
                if container.status == expected_status:
                    return True, None
                elif container.status in ["exited", "dead"]:
                    logs = container.logs(tail=50).decode("utf-8")
                    return False, f"容器异常退出，状态: {container.status}\n最后50行日志:\n{logs}"
            except NotFound:
                if expected_status == "removed":
                    return True, None
                return False, "容器不存在"
            except Exception as e:
                return False, f"检查容器状态失败: {str(e)}"
            time.sleep(1)

        return False, f"等待容器状态 {expected_status} 超时"

    def start_container(self, compose_file: str = "docker-compose.yml") -> bool:
        """
        启动容器

        Args:
            compose_file: Docker Compose文件路径，相对于项目目录

        Returns:
            bool: 是否启动成功
        """
        try:
            self.compose_file = self.project_dir / compose_file
            if not self.compose_file.exists():
                raise ContainerError(f"Docker Compose文件不存在: {self.compose_file}")

            # 检查容器是否已经在运行
            try:
                container = self.docker_client.containers.get(self.container_name)
                if container.status == "running":
                    logger.warning("容器已经在运行中")
                    # 如果是通过状态检查后选择重启的情况，先停止容器
                    if hasattr(self, "_is_restart") and self._is_restart:
                        logger.warning("正在停止容器...")
                        run_command(f"docker compose -f {self.compose_file} down", shell=True)
                        success, error = self._wait_for_container_status("removed")
                        if not success:
                            raise ContainerError(error)
                        delattr(self, "_is_restart")
                    else:
                        return True
            except NotFound:
                pass

            logger.warning("启动容器...")
            run_command(f"docker compose -f {self.compose_file} up -d", shell=True)

            success, error = self._wait_for_container_status("running")
            if not success:
                raise ContainerError(error)

            # 记录日志但不输出到控制台
            logger.info("容器启动成功")
            return True

        except Exception as e:
            logger.error(f"启动容器失败: {e}")
            return False

    def stop_container(self) -> bool:
        """
        停止容器

        Returns:
            bool: 是否停止成功
        """
        try:
            # 如果compose_file未设置，尝试在项目目录中查找
            if not self.compose_file:
                default_compose_file = self.project_dir / "docker-compose.yml"
                if default_compose_file.exists():
                    self.compose_file = default_compose_file
                else:
                    raise ContainerError("未找到Docker Compose文件，请确保docker-compose.yml存在")

            logger.warning("停止容器...")
            run_command(f"docker compose -f {self.compose_file} down", shell=True)

            success, error = self._wait_for_container_status("removed")
            if not success:
                raise ContainerError(error)

            # 记录日志但不输出到控制台
            logger.info("容器已停止")
            return True

        except Exception as e:
            logger.error(f"停止容器失败: {e}")
            return False

    def save_as_image(self, image_name: Optional[str] = None, cleanup: bool = False) -> str:
        """
        将当前运行的容器保存为新的镜像
        
        此方法已废弃，请使用ImageManager.create_from_container方法

        Args:
            image_name: 可选，新镜像的名称，格式为 "repository:tag"。如果未指定，将使用容器名称作为repository，时间戳作为tag
            cleanup: 是否在保存前清理容器

        Returns:
            str: 成功时返回新镜像的名称
        """
        # 使用新的ImageManager实现
        logger.warning("此方法已废弃，请使用ImageManager.create_from_container方法")
        
        try:
            # 处理参数
            tag = None
            repository = None
            
            if image_name:
                if ":" in image_name:
                    repository, tag = image_name.split(":", 1)
                else:
                    repository = image_name
            
            # 创建ImageManager实例
            image_manager = ImageManager(str(self.project_dir))
            return image_manager.create_from_container(
                self.container_name, 
                tag=tag,
                repository=repository,
                cleanup=cleanup
            )
        except Exception as e:
            logger.error(f"保存容器为镜像失败: {e}")
            return False

    def cleanup_container(self, paths: Optional[List[str]] = None) -> bool:
        """
        清理容器内的缓存文件

        Args:
            paths: 要清理的路径列表，如果为None则使用默认路径

        Returns:
            bool: 是否清理成功
        """
        try:
            container = self.docker_client.containers.get(self.container_name)

            if not paths:
                paths = ["/tmp/*", "/var/cache/*"]

            logger.warning("清理容器缓存...")
            for path in paths:
                try:
                    container.exec_run(f"rm -rf {path}")
                except Exception as e:
                    logger.error(f"清理路径 {path} 失败: {e}")

            logger.success("容器缓存清理完成")
            return True

        except Exception as e:
            logger.error(f"清理容器失败: {e}")
            return False

    def schedule_backup(
        self,
        schedule_config: Union[str, Dict[str, Any]],
        image_name: Optional[str] = None,
        cleanup: bool = False,
        auto_push: bool = False,
    ) -> str:
        """
        设置定时备份任务
        
        此方法已废弃，请使用SchedulerManager.schedule_backup方法

        Args:
            schedule_config: 定时配置，可以是字符串(向后兼容)或字典
            image_name: 备份镜像名称，如果为None则使用容器名称加时间戳
            cleanup: 是否在备份前清理容器
            auto_push: 是否自动推送备份镜像

        Returns:
            str: 成功返回job_id，失败返回False
        """
        logger.warning("此方法已废弃，请使用SchedulerManager.schedule_backup方法")
        return self.scheduler_manager.schedule_backup(schedule_config, image_name, cleanup, auto_push)

    def schedule_cleanup(
        self, schedule_config: Union[str, Dict[str, Any]], paths: Optional[List[str]] = None
    ) -> str:
        """
        设置定时清理任务
        
        此方法已废弃，请使用SchedulerManager.schedule_cleanup方法

        Args:
            schedule_config: 定时配置，可以是字符串(向后兼容)或字典
            paths: 要清理的路径列表

        Returns:
            str: 成功返回job_id，失败返回False
        """
        logger.warning("此方法已废弃，请使用SchedulerManager.schedule_cleanup方法")
        return self.scheduler_manager.schedule_cleanup(schedule_config, paths)

    def list_scheduled_tasks(self) -> Dict[str, Any]:
        """
        列出所有定时任务
        
        此方法已废弃，请使用SchedulerManager.list_scheduled_tasks方法

        Returns:
            Dict[str, Any]: 任务信息字典
        """
        logger.warning("此方法已废弃，请使用SchedulerManager.list_scheduled_tasks方法")
        return self.scheduler_manager.list_scheduled_tasks()

    def remove_scheduled_task(self, task_type: str) -> bool:
        """
        删除定时任务
        
        此方法已废弃，请使用SchedulerManager.remove_scheduled_task方法

        Args:
            task_type: 任务类型 (backup/cleanup)

        Returns:
            bool: 是否成功删除
        """
        logger.warning("此方法已废弃，请使用SchedulerManager.remove_scheduled_task方法")
        return self.scheduler_manager.remove_scheduled_task(task_type)

    def show_logs(self, follow: bool = False) -> bool:
        """
        显示容器日志
        
        此方法已废弃，请使用ContainerMonitor.show_logs方法

        Args:
            follow: 是否持续显示日志

        Returns:
            bool: 是否成功显示日志
        """
        logger.warning("此方法已废弃，请使用ContainerMonitor.show_logs方法")
        return self.monitor.show_logs(follow=follow)

    def start_scheduler(self) -> bool:
        """
        启动调度器守护进程
        
        此方法已废弃，请使用SchedulerManager.start_scheduler方法

        Returns:
            bool: 是否成功启动
        """
        logger.warning("此方法已废弃，请使用SchedulerManager.start_scheduler方法")
        return self.scheduler_manager.start_scheduler()

    def stop_scheduler(self) -> bool:
        """
        停止调度器守护进程
        
        此方法已废弃，请使用SchedulerManager.stop_scheduler方法

        Returns:
            bool: 是否成功停止
        """
        logger.warning("此方法已废弃，请使用SchedulerManager.stop_scheduler方法")
        return self.scheduler_manager.stop_scheduler()

    def restart_scheduler(self) -> bool:
        """
        重启调度器守护进程
        
        此方法已废弃，请使用SchedulerManager.restart_scheduler方法

        Returns:
            bool: 是否成功重启
        """
        logger.warning("此方法已废弃，请使用SchedulerManager.restart_scheduler方法")
        return self.scheduler_manager.restart_scheduler()

    def is_scheduler_running(self) -> bool:
        """
        检查调度器是否在运行
        
        此方法已废弃，请使用SchedulerManager.is_scheduler_running方法

        Returns:
            bool: 是否在运行
        """
        logger.warning("此方法已废弃，请使用SchedulerManager.is_scheduler_running方法")
        return self.scheduler_manager.is_scheduler_running()

    def get_scheduler_status(self) -> Dict[str, Any]:
        """
        获取调度器状态信息
        
        此方法已废弃，请使用SchedulerManager.get_scheduler_status方法

        Returns:
            Dict[str, Any]: 状态信息
        """
        logger.warning("此方法已废弃，请使用SchedulerManager.get_scheduler_status方法")
        return self.scheduler_manager.get_scheduler_status()

    def get_scheduler_logs(self, task_type: str = None, lines: int = 100) -> str:
        """
        获取调度器日志
        
        此方法已废弃，请使用SchedulerManager.get_scheduler_logs方法

        Args:
            task_type: 任务类型，如果为None则返回调度器主日志
            lines: 返回的日志行数

        Returns:
            str: 日志内容
        """
        logger.warning("此方法已废弃，请使用SchedulerManager.get_scheduler_logs方法")
        return self.scheduler_manager.get_scheduler_logs(task_type, lines)
