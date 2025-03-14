"""容器管理器类"""

import os
import time
import docker
import schedule
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple, Union, Callable
from docker.errors import APIError, NotFound
from requests.exceptions import RequestException

from .base_manager import BaseManager
from .image_manager import ImageManager
from .scheduler_daemon import SchedulerDaemon
from loguru import logger
from ..utils import run_command, confirm_action, get_timestamp
import typer

class ContainerError(Exception):
    """容器操作错误"""
    pass

class ContainerManager(BaseManager):
    """容器管理器类，用于管理容器的生命周期和维护"""
    
    MAX_RETRIES = 3
    RETRY_DELAY = 2
    STARTUP_TIMEOUT = 30
    
    def __init__(self, project_dir: str, container_name: str):
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
        self._check_docker_connection()
        self.scheduler_daemon = SchedulerDaemon(project_dir)
        
    def _check_docker_connection(self):
        """检查Docker守护进程连接"""
        try:
            self.docker_client.ping()
        except (APIError, RequestException) as e:
            raise ContainerError(f"无法连接到Docker守护进程: {str(e)}")
    
    def _wait_for_container_status(self, expected_status: str, timeout: int = None) -> Tuple[bool, Optional[str]]:
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
                    logs = container.logs(tail=50).decode('utf-8')
                    return False, f"容器异常退出，状态: {container.status}\n最后50行日志:\n{logs}"
            except NotFound:
                if expected_status == "removed":
                    return True, None
                return False, "容器不存在"
            except Exception as e:
                return False, f"检查容器状态失败: {str(e)}"
            time.sleep(1)
        
        return False, f"等待容器状态 {expected_status} 超时"
    
    def start_container(self, compose_file: str = 'docker-compose.yml') -> bool:
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
            if not self.compose_file:
                raise ContainerError("未指定Docker Compose文件")
            
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
    
    def save_as_image(self, image_name: str = None, cleanup: bool = False) -> Union[str, bool]:
        """
        将当前运行的容器保存为新的镜像
        
        Args:
            image_name: 可选，新镜像的名称，格式为 "repository:tag"。如果未指定，将使用容器名称作为repository，时间戳作为tag
            cleanup: 是否在保存前清理容器
            
        Returns:
            str: 成功时返回新镜像的名称
            bool: 失败时返回False
        """
        try:
            container = self.docker_client.containers.get(self.container_name)
            
            if cleanup:
                logger.warning("清理容器...")
                if not self.cleanup_container():
                    logger.warning("清理容器失败，继续保存")
            
            # 如果没有指定镜像名称，则使用容器名称作为repository，时间戳作为tag
            if not image_name:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                repository = self.container_name
                tag = timestamp
            else:
                # 如果指定了镜像名称，解析repository和tag
                if ':' in image_name:
                    repository, tag = image_name.split(':', 1)
                else:
                    repository = image_name
                    # 如果没有指定tag，使用日期时间作为tag
                    tag = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            versioned_image_name = f"{repository}:{tag}"
            logger.warning(f"将容器保存为镜像 {versioned_image_name}...")
            
            # 提交容器为新镜像，添加进度提示
            logger.warning("正在提交容器状态...")
            import time
            start_time = time.time()
            
            # 使用低级API提交容器
            response = self.docker_client.api.commit(
                container=self.container_name,
                repository=repository,
                tag=tag
            )
            
            # 获取新创建的镜像ID
            image_id = response.get('Id', '').split(':')[-1][:12]
            
            # 计算耗时
            elapsed_time = time.time() - start_time
            logger.warning(f"容器状态提交完成，耗时 {elapsed_time:.2f} 秒，镜像ID: {image_id}")
            
            # 同时设置latest标签
            latest_image_name = f"{repository}:latest"
            try:
                logger.warning("正在设置latest标签...")
                image = self.docker_client.images.get(versioned_image_name)
                image.tag(repository=repository, tag="latest")
                logger.success(f"已为镜像 {versioned_image_name} 添加标签 {latest_image_name}")
            except Exception as e:
                logger.error(f"设置latest标签失败: {e}")
            
            logger.success(f"容器已保存为镜像 {versioned_image_name}")
            return versioned_image_name
            
        except Exception as e:
            logger.error(f"保存容器为镜像失败: {e}")
            return False
    
    def cleanup_container(self, paths: List[str] = None) -> bool:
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
                paths = ['/tmp/*', '/var/cache/*']
            
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
    
    def schedule_backup(self, schedule_config: Union[str, Dict[str, Any]], image_name: str = None,
                       cleanup: bool = False, auto_push: bool = False) -> bool:
        """
        设置定时备份任务
        
        Args:
            schedule_config: 定时配置，可以是字符串(向后兼容)或字典
            image_name: 备份镜像名称，如果为None则使用容器名称加时间戳
            cleanup: 是否在备份前清理容器
            auto_push: 是否自动推送备份镜像
            
        Returns:
            bool: 是否设置成功
        """
        # 如果启用了自动推送，验证推送所需的配置
        if auto_push:
            # 从配置文件中获取镜像仓库信息
            config_path = os.path.join(self.project_dir, "config.json")
            registry = None
            username = None
            password = None
            
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    if 'image' in config and 'registry' in config['image']:
                        registry = config['image']['registry'].get('url')
                        username = config['image']['registry'].get('username')
                        prefix = config['image']['registry'].get('prefix')
                        # 优先从环境变量获取密码
                        env_var_name = f"DOCKER_PASSWORD_{username.upper()}" if username else "DOCKER_PASSWORD"
                        password = os.environ.get(env_var_name) or config['image']['registry'].get('password')
            
            # 验证推送配置是否完整
            if not registry or not username or not password:
                logger.warning("启用自动推送但仓库配置不完整")
                logger.warning("请确保在配置文件中设置了 registry.url 和 registry.username")
                logger.warning("密码可以通过环境变量设置，避免明文存储")
                logger.warning(f"可以设置环境变量 {env_var_name if username else 'DOCKER_PASSWORD'} 来提供密码")
                logger.warning("或者使用 docker login 命令登录")
                logger.warning("继续设置定时备份任务，但自动推送可能会失败")
        
        def backup_job():
            # 直接调用save_as_image方法，它已经实现了自动生成日期时间标签的功能
            saved_image_name = self.save_as_image(image_name, cleanup=cleanup)
            if saved_image_name and auto_push:
                # 实现推送逻辑
                try:
                    # 从配置文件中获取镜像仓库信息
                    config_path = os.path.join(self.project_dir, "config.json")
                    registry = None
                    username = None
                    password = None
                    
                    if os.path.exists(config_path):
                        with open(config_path, 'r', encoding='utf-8') as f:
                            config = json.load(f)
                            if 'image' in config and 'registry' in config['image']:
                                registry = config['image']['registry'].get('url')
                                username = config['image']['registry'].get('username')
                                prefix = config['image']['registry'].get('prefix')
                                # 优先从环境变量获取密码
                                env_var_name = f"DOCKER_PASSWORD_{username.upper()}" if username else "DOCKER_PASSWORD"
                                password = os.environ.get(env_var_name) or config['image']['registry'].get('password')
                    
                    # 创建ImageManager实例并推送镜像
                    image_manager = ImageManager(self.project_dir, saved_image_name)
                    if image_manager.push_image(registry, username, password, prefix=prefix):
                        logger.success(f"备份镜像 {saved_image_name} 推送成功")
                    else:
                        logger.error(f"备份镜像 {saved_image_name} 推送失败")
                except Exception as e:
                    logger.error(f"推送备份镜像失败: {e}")
        
        extra_info = {
            "cleanup": cleanup,
            "auto_push": auto_push,
            "image_name": image_name
        }
        
        # 创建任务
        job = self._schedule_task("backup", schedule_config, backup_job, extra_info)
        
        # 询问是否立即启动调度器
        if job and not self.is_scheduler_running():
            if typer.confirm("调度器未运行，是否立即启动?"):
                return self.start_scheduler()
        
        return job is not None
    
    def schedule_cleanup(self, schedule_config: Union[str, Dict[str, Any]], paths: List[str] = None) -> bool:
        """
        设置定时清理任务
        
        Args:
            schedule_config: 定时配置，可以是字符串(向后兼容)或字典
            paths: 要清理的路径列表
            
        Returns:
            bool: 是否设置成功
        """
        if not paths:
            paths = ["/tmp/*", "/var/cache/*"]
            
        def cleanup_job():
            self.cleanup_container(paths)
        
        extra_info = {
            "paths": paths
        }
        
        # 创建任务
        job = self._schedule_task("cleanup", schedule_config, cleanup_job, extra_info)
        
        # 询问是否立即启动调度器
        if job and not self.is_scheduler_running():
            if typer.confirm("调度器未运行，是否立即启动?"):
                return self.start_scheduler()
        
        return job is not None
    
    def _schedule_task(self, task_type: str, schedule_config: Union[str, Dict[str, Any]], 
                     job_func: Callable, extra_info: Dict[str, Any] = None) -> Optional[schedule.Job]:
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
                if re.match(r'^([0-1]?[0-9]|2[0-3]):([0-5][0-9])(:([0-5][0-9]))?$', schedule_config):
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
                    job = schedule.every().day.at(time).do(
                        lambda: job_func() if datetime.now().day == day else None
                    )
                
                elif schedule_type == "hourly":
                    minute = schedule_config.get("minute", 0)
                    job = schedule.every().hour.at(f":{minute:02d}").do(job_func)
                
                else:
                    raise ValueError(f"不支持的定时类型: {schedule_type}")
            
            if not job:
                raise ValueError(f"无法设置定时任务: {schedule_config}")
            
            # 生成新的任务ID
            import uuid
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
    
    def _save_schedule_info(self, task_type: str, cron_expr: str, job_id: Optional[str] = None, extra_info: Dict[str, Any] = None) -> None:
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
                import uuid
                job_id = f"{task_type}_{uuid.uuid4().hex[:8]}"
            
            # 获取项目配置
            config_path = os.path.join(self.project_dir, "config.json")
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
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
                **(extra_info or {})
            }
            
            # 写入配置文件
            with open(config_path, 'w', encoding='utf-8') as f:
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
                with open(config_path, 'r', encoding='utf-8') as f:
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
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                if "schedule" in config and task_type in config["schedule"]:
                    del config["schedule"][task_type]
                    
                    # 写回配置文件
                    with open(config_path, 'w', encoding='utf-8') as f:
                        json.dump(config, f, indent=2, ensure_ascii=False)
            
            logger.success(f"已删除 {task_type} 定时任务")
            return True
            
        except Exception as e:
            logger.error(f"删除定时任务失败: {e}")
            return False
            
    def show_logs(self, follow: bool = False) -> bool:
        """
        显示容器日志
        
        Args:
            follow: 是否持续显示日志
            
        Returns:
            bool: 是否成功显示日志
        """
        try:
            container = self.docker_client.containers.get(self.container_name)
            
            if container.status != "running":
                logger.warning(f"容器 {self.container_name} 未运行")
                return False
            
            logger.debug(f"显示容器 {self.container_name} 的日志:")
            
            if follow:
                # 持续显示日志
                for line in container.logs(stream=True, follow=True):
                    print(line.decode('utf-8').strip())
            else:
                # 显示最近的日志
                logs = container.logs(tail=100).decode('utf-8')
                print(logs)
            
            return True
            
        except Exception as e:
            logger.error(f"显示容器日志失败: {e}")
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
        if status.get('status') == 'running' and 'start_time' in status:
            start_time = datetime.strptime(status['start_time'], "%Y-%m-%d %H:%M:%S")
            now = datetime.now()
            delta = now - start_time
            days = delta.days
            hours = delta.seconds // 3600
            minutes = (delta.seconds % 3600) // 60
            
            status['uptime'] = {
                'days': days,
                'hours': hours,
                'minutes': minutes,
                'formatted': f"{days}天{hours}小时{minutes}分钟"
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