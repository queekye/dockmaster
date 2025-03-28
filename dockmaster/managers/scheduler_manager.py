"""调度任务管理器，负责容器的定时任务管理"""

import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union, TypedDict, Literal

import schedule
import typer
from loguru import logger

from .base_manager import BaseManager
from .scheduler_daemon import SchedulerDaemon
from .image_manager import ImageManager
from ..constants import ERROR_MESSAGES


class ScheduleConfig(TypedDict, total=False):
    """定时任务配置类型"""
    type: Literal['daily', 'weekly', 'monthly', 'hourly']
    time: str
    weekday: str
    day: int
    minute: int


class SchedulerManager(BaseManager):
    """调度任务管理器类，用于管理容器相关的定时任务"""
    
    project_dir: Path
    scheduler_daemon: SchedulerDaemon
    container_name: str
    
    def __init__(self, project_dir: str, container_name: str) -> None:
        """
        初始化调度任务管理器
        
        Args:
            project_dir: 项目目录路径
            container_name: 容器名称
        """
        super().__init__()
        self.project_dir = Path(project_dir)
        self.scheduler_daemon = SchedulerDaemon(project_dir)
        self.container_name = container_name

    def schedule_backup(
        self,
        schedule_config: Union[str, ScheduleConfig],
        image_name: Optional[str] = None,
        cleanup: bool = False,
        auto_push: bool = False,
    ) -> str:
        """
        设置定时备份任务

        Args:
            schedule_config: 定时配置，可以是字符串(向后兼容)或字典
            image_name: 备份镜像名称，如果为None则使用容器名称加时间戳
            cleanup: 是否在备份前清理容器
            auto_push: 是否自动推送备份镜像

        Returns:
            str: 成功返回job_id，失败返回False
        """
        # 验证推送配置
        if auto_push:
            # 从配置文件中获取镜像仓库信息
            config_path = os.path.join(self.project_dir, "config.json")
            registry = None
            username = None
            password = None

            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    if "image" in config and "registry" in config["image"]:
                        registry = config["image"]["registry"].get("url")
                        username = config["image"]["registry"].get("username")
                        prefix = config["image"]["registry"].get("prefix")
                        # 优先从环境变量获取密码
                        env_var_name = (
                            f"DOCKER_PASSWORD_{username.upper()}" if username else "DOCKER_PASSWORD"
                        )
                        password = os.environ.get(env_var_name) or config["image"]["registry"].get(
                            "password"
                        )

            # 验证推送配置是否完整
            if not registry or not username or not password:
                logger.warning("启用自动推送但仓库配置不完整")
                logger.warning("请确保在配置文件中设置了 registry.url 和 registry.username")
                logger.warning("密码可以通过环境变量设置，避免明文存储")
                logger.warning(
                    f"可以设置环境变量 {env_var_name if username else 'DOCKER_PASSWORD'} 来提供密码"
                )
                logger.warning("继续设置定时备份任务，但自动推送可能会失败")
                
        # 定义备份作业函数
        def backup_job():
            # 导入这里以避免循环依赖
            from .container_manager import ContainerManager
            
            try:
                # 创建ContainerManager实例
                container_manager = ContainerManager(str(self.project_dir), self.container_name)
                
                # 如果需要清理，先清理容器
                if cleanup:
                    logger.warning("清理容器...")
                    container_manager.cleanup_container()
                
                # 保存镜像
                # 导入ImageManager执行备份
                image_manager = ImageManager(str(self.project_dir))
                saved_image = image_manager.create_from_container(
                    self.container_name, 
                    tag=None if not image_name else image_name.split(":")[-1] if ":" in image_name else None,
                    repository=None if not image_name else image_name.split(":")[0] if ":" in image_name else image_name
                )
                
                if not saved_image:
                    logger.error("备份容器失败")
                    return
                
                # 自动推送
                if auto_push and saved_image:
                    try:
                        # 从配置文件中获取镜像仓库信息
                        config_path = os.path.join(self.project_dir, "config.json")
                        registry = None
                        username = None
                        password = None
                        prefix = None

                        if os.path.exists(config_path):
                            with open(config_path, "r", encoding="utf-8") as f:
                                config = json.load(f)
                                if "image" in config and "registry" in config["image"]:
                                    registry = config["image"]["registry"].get("url")
                                    username = config["image"]["registry"].get("username")
                                    prefix = config["image"]["registry"].get("prefix")
                                    # 优先从环境变量获取密码
                                    env_var_name = (
                                        f"DOCKER_PASSWORD_{username.upper()}"
                                        if username
                                        else "DOCKER_PASSWORD"
                                    )
                                    password = os.environ.get(env_var_name) or config["image"][
                                        "registry"
                                    ].get("password")
                        
                        # 推送镜像
                        if image_manager.push_image(registry, username, password, prefix=prefix, use_existing_tags=True):
                            logger.success(f"备份镜像 {saved_image} 推送成功")
                        else:
                            logger.error(f"备份镜像 {saved_image} 推送失败")
                    except Exception as e:
                        logger.error(f"推送备份镜像失败: {e}")
            except Exception as e:
                logger.error(f"执行备份任务失败: {e}")

        # 创建任务的额外信息
        extra_info = {"cleanup": cleanup, "auto_push": auto_push, "image_name": image_name}

        # 创建定时任务
        job = self._schedule_task("backup", schedule_config, backup_job, extra_info)

        # 询问是否立即启动调度器
        if job and not self.is_scheduler_running():
            if typer.confirm("调度器未运行，是否立即启动?"):
                self.start_scheduler()

        # 返回job_id
        return getattr(job, "job_id", None) if job else False

    def schedule_cleanup(
        self, schedule_config: Union[str, ScheduleConfig], paths: Optional[List[str]] = None
    ) -> str:
        """
        设置定时清理任务

        Args:
            schedule_config: 定时配置，可以是字符串(向后兼容)或字典
            paths: 要清理的路径列表

        Returns:
            str: 成功返回job_id，失败返回False
        """
        if not paths:
            paths = ["/tmp/*", "/var/cache/*"]

        def cleanup_job():
            # 导入这里以避免循环依赖
            from .container_manager import ContainerManager
            
            try:
                # 创建ContainerManager实例清理容器
                container_manager = ContainerManager(str(self.project_dir), self.container_name)
                container_manager.cleanup_container(paths)
            except Exception as e:
                logger.error(f"执行清理任务失败: {e}")

        extra_info = {"paths": paths}

        # 创建任务
        job = self._schedule_task("cleanup", schedule_config, cleanup_job, extra_info)

        # 询问是否立即启动调度器
        if job and not self.is_scheduler_running():
            if typer.confirm("调度器未运行，是否立即启动?"):
                self.start_scheduler()

        # 返回job_id
        return getattr(job, "job_id", None) if job else False

    def _schedule_task(
        self,
        task_type: str,
        schedule_config: Union[str, ScheduleConfig],
        job_func: Callable[[], Any],
        extra_info: Optional[Dict[str, Any]] = None,
    ) -> Optional[schedule.Job]:
        """
        通用的定时任务设置方法

        Args:
            task_type: 任务类型 (backup/cleanup)
            schedule_config: 定时配置，可以是字符串(向后兼容)或字典
            job_func: 要执行的任务函数
            extra_info: 额外信息，保存到配置文件中

        Returns:
            Optional[schedule.Job]: 成功返回任务对象，失败返回None
        """
        try:
            # 检查是否存在同类型的旧任务，如果存在则先删除
            tasks = self.list_scheduled_tasks()
            if task_type in tasks:
                logger.info(f"检测到已存在的 {task_type} 任务，正在删除...")
                # 从schedule库中移除任务
                job_id = tasks[task_type].get("job_id")
                if job_id:
                    for job in schedule.jobs:
                        if getattr(job, "job_id", None) == job_id:
                            schedule.cancel_job(job)
                            break
                logger.info(f"已删除旧的 {task_type} 任务")

            # 解析定时配置并设置定时任务
            job = None

            # 向后兼容：如果是字符串，假设是时间格式 (HH:MM)
            if isinstance(schedule_config, str):
                # 验证时间格式
                import re

                if re.match(
                    r"^([0-1]?[0-9]|2[0-3]):([0-5][0-9])(:([0-5][0-9]))?$", schedule_config
                ):
                    job = schedule.every().day.at(schedule_config).do(job_func)
                else:
                    raise ValueError(f"无效的时间格式: {schedule_config}，请使用 HH:MM 格式")
            else:
                # 新格式：字典配置
                schedule_type = schedule_config.get("type")

                if schedule_type == "daily":
                    time = schedule_config.get("time", "00:00")
                    job = schedule.every().day.at(time).do(job_func)

                elif schedule_type == "weekly":
                    weekday = schedule_config.get("weekday", "monday")
                    time = schedule_config.get("time", "00:00")
                    weekday_method = getattr(schedule.every(), weekday)
                    job = weekday_method.at(time).do(job_func)

                elif schedule_type == "monthly":
                    day = schedule_config.get("day", 1)
                    time = schedule_config.get("time", "00:00")
                    # schedule库不直接支持每月执行，使用自定义逻辑
                    job = (
                        schedule.every()
                        .day.at(time)
                        .do(lambda: job_func() if datetime.now().day == day else None)
                    )

                elif schedule_type == "hourly":
                    minute = schedule_config.get("minute", 0)
                    job = schedule.every().hour.at(f":{minute:02d}").do(job_func)

                else:
                    raise ValueError(f"不支持的定时类型: {schedule_type}")

            if not job:
                raise ValueError(f"无法设置定时任务: {schedule_config}")

            # 生成新的任务ID
            job_id = f"{task_type}_{uuid.uuid4().hex[:8]}"
            setattr(job, "job_id", job_id)

            # 设置任务类型属性，用于日志记录
            setattr(job, "task_type", task_type)

            # 保存任务信息到配置文件
            self._save_schedule_info(task_type, str(schedule_config), job_id, extra_info)

            logger.success(f"已设置定时{task_type}任务: {schedule_config}")
            return job

        except Exception as e:
            logger.error(f"设置定时{task_type}任务失败: {e}")
            return None

    def _save_schedule_info(
        self,
        task_type: str,
        cron_expr: str,
        job_id: Optional[str] = None,
        extra_info: Dict[str, Any] = None,
    ) -> None:
        """
        保存定时任务信息到配置文件

        Args:
            task_type: 任务类型
            cron_expr: cron表达式或时间配置
            job_id: 任务ID（可选）
            extra_info: 额外信息
        """
        try:
            # 如果没有提供job_id，生成一个唯一的ID
            if not job_id:
                job_id = f"{task_type}_{uuid.uuid4().hex[:8]}"

            # 获取项目配置
            config_path = os.path.join(self.project_dir, "config.json")
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
            else:
                config = {}

            # 确保配置中有schedule部分
            if "schedule" not in config:
                config["schedule"] = {}

            # 保存任务信息
            config["schedule"][task_type] = {
                "cron": cron_expr,
                "job_id": job_id,
                "container_name": self.container_name,
                **(extra_info or {}),
            }

            # 写入配置文件
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)

        except Exception as e:
            logger.error(f"保存定时任务信息失败: {e}")

    def list_scheduled_tasks(self) -> Dict[str, Any]:
        """
        列出所有定时任务

        Returns:
            Dict[str, Any]: 任务信息字典
        """
        try:
            config_path = os.path.join(self.project_dir, "config.json")
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)

                if "schedule" in config:
                    return config["schedule"]

            return {}

        except Exception as e:
            logger.error(f"获取定时任务列表失败: {e}")
            return {}

    def remove_scheduled_task(self, task_type: str) -> bool:
        """
        删除定时任务

        Args:
            task_type: 任务类型 (backup/cleanup)

        Returns:
            bool: 是否成功删除
        """
        try:
            # 获取任务信息
            tasks = self.list_scheduled_tasks()
            if task_type not in tasks:
                logger.warning(f"未找到类型为 {task_type} 的定时任务")
                return False

            # 从schedule库中移除任务
            job_id = tasks[task_type].get("job_id")
            if job_id:
                # 查找并移除对应的任务
                for job in schedule.jobs:
                    if getattr(job, "job_id", None) == job_id:
                        schedule.cancel_job(job)
                        break

            # 从配置中移除任务信息
            config_path = os.path.join(self.project_dir, "config.json")
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)

                if "schedule" in config and task_type in config["schedule"]:
                    del config["schedule"][task_type]

                    # 写回配置文件
                    with open(config_path, "w", encoding="utf-8") as f:
                        json.dump(config, f, indent=2, ensure_ascii=False)

            logger.success(f"已删除 {task_type} 定时任务")
            return True

        except Exception as e:
            logger.error(f"删除定时任务失败: {e}")
            return False
            
    def start_scheduler(self) -> bool:
        """
        启动调度器守护进程

        Returns:
            bool: 是否成功启动
        """
        success = self.scheduler_daemon.start()
        if success:
            logger.success("调度器已启动")
        return success

    def stop_scheduler(self) -> bool:
        """
        停止调度器守护进程

        Returns:
            bool: 是否成功停止
        """
        return self.scheduler_daemon.stop()

    def restart_scheduler(self) -> bool:
        """
        重启调度器守护进程

        Returns:
            bool: 是否成功重启
        """
        return self.scheduler_daemon.restart()

    def is_scheduler_running(self) -> bool:
        """
        检查调度器是否在运行

        Returns:
            bool: 是否在运行
        """
        return self.scheduler_daemon.is_running()

    def get_scheduler_status(self) -> Dict[str, Any]:
        """
        获取调度器状态信息

        Returns:
            Dict[str, Any]: 状态信息
        """
        status = self.scheduler_daemon.get_status()

        # 计算运行时间
        if status.get("status") == "running" and "start_time" in status:
            start_time = datetime.strptime(status["start_time"], "%Y-%m-%d %H:%M:%S")
            now = datetime.now()
            delta = now - start_time
            days = delta.days
            hours = delta.seconds // 3600
            minutes = (delta.seconds % 3600) // 60

            status["uptime"] = {
                "days": days,
                "hours": hours,
                "minutes": minutes,
                "formatted": f"{days}天{hours}小时{minutes}分钟",
            }

        return status

    def get_scheduler_logs(self, task_type: str = None, lines: int = 100) -> str:
        """
        获取调度器日志

        Args:
            task_type: 任务类型，如果为None则返回调度器主日志
            lines: 返回的日志行数

        Returns:
            str: 日志内容
        """
        return self.scheduler_daemon.get_logs(task_type, lines) 