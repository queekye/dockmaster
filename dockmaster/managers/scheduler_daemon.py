"""调度器守护进程模块"""

import json
import os
import signal
import time
import traceback
from datetime import datetime
from pathlib import Path
from subprocess import check_output
from typing import Any, Callable, Dict, Optional, TypedDict, Union, List, NoReturn

import daemon
import daemon.pidfile
import schedule
from loguru import logger


class TaskHistory(TypedDict):
    """任务历史记录类型"""
    status: str
    start_time: str
    end_time: str
    error: Optional[str]


class TaskInfo(TypedDict):
    """任务信息类型"""
    job_id: str
    cron_expr: str
    last_run: Optional[str]
    next_run: Optional[str]
    history: List[TaskHistory]


class SchedulerStatus(TypedDict):
    """调度器状态类型"""
    status: str
    start_time: Optional[str]
    stop_time: Optional[str]
    tasks: Dict[str, TaskInfo]


class SchedulerDaemon:
    """调度器守护进程类"""

    project_dir: Path
    logs_dir: Path
    tasks_dir: Path
    pid_file: Path
    status_file: Path
    log_file: Path
    running: bool

    def __init__(self, project_dir: str) -> None:
        """
        初始化调度器守护进程

        Args:
            project_dir: 项目目录路径
        """
        self.project_dir = Path(project_dir)
        # 创建日志目录结构
        self.logs_dir = self.project_dir / "logs" / "scheduler"
        self.tasks_dir = self.logs_dir / "tasks"
        self.pid_file = self.logs_dir / "scheduler.pid"
        self.status_file = self.logs_dir / "scheduler.status"
        self.log_file = self.logs_dir / "scheduler.log"

        # 确保目录存在
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        (self.tasks_dir / "backup").mkdir(exist_ok=True)
        (self.tasks_dir / "cleanup").mkdir(exist_ok=True)

        self.running = False

    def _update_status(self, status: Optional[str] = None, task_info: Optional[Dict[str, Any]] = None) -> None:
        """
        更新调度器状态文件

        Args:
            status: 调度器状态
            task_info: 任务相关信息

        Raises:
            Exception: 更新状态失败时抛出
        """
        try:
            # 读取当前状态
            current_status = {}
            if self.status_file.exists():
                with open(self.status_file, "r", encoding="utf-8") as f:
                    current_status = json.load(f)

            # 更新状态
            if status:
                current_status["status"] = status
                if status == "running":
                    current_status["start_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                elif status == "stopped":
                    current_status["stop_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 更新任务信息
            if task_info:
                if "tasks" not in current_status:
                    current_status["tasks"] = {}
                for task_type, info in task_info.items():
                    if task_type not in current_status["tasks"]:
                        current_status["tasks"][task_type] = {}
                    current_status["tasks"][task_type].update(info)

            # 写入状态文件
            with open(self.status_file, "w", encoding="utf-8") as f:
                json.dump(current_status, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error(f"更新调度器状态失败: {e}")

    def _get_task_logger(self, task_type: str) -> logger:
        """
        获取任务专用的日志记录器

        Args:
            task_type: 任务类型

        Returns:
            logger: 日志记录器
        """
        task_dir = self.tasks_dir / task_type
        latest_log = task_dir / "latest.log"
        history_log = task_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

        # 创建新的日志记录器
        task_logger = logger.bind(task=task_type)

        # 添加日志处理器
        task_logger.add(str(latest_log), rotation="1 day", retention="7 days")
        task_logger.add(str(history_log), retention="30 days")

        return task_logger

    def _update_task_history(self, task_type: str, status: str, error: str = None) -> None:
        """
        更新任务执行历史

        Args:
            task_type: 任务类型
            status: 执行状态
            error: 错误信息（如果有）
        """
        try:
            history_file = self.tasks_dir / task_type / "history.json"
            history = []

            # 读取现有历史记录
            if history_file.exists():
                with open(history_file, "r", encoding="utf-8") as f:
                    history = json.load(f)

            # 添加新记录
            history.append(
                {
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "status": status,
                    "error": error,
                }
            )

            # 只保留最近30条记录
            if len(history) > 30:
                history = history[-30:]

            # 保存历史记录
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2, ensure_ascii=False)

            # 更新调度器状态
            self._update_status(
                task_info={
                    task_type: {
                        "last_run": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "status": status,
                        "last_error": error,
                    }
                }
            )

        except Exception as e:
            logger.error(f"更新任务历史失败: {e}")

    def _run_task_with_logging(self, task_type: str, task_func: Callable[[], Any]) -> None:
        """
        执行任务并记录日志

        Args:
            task_type: 任务类型
            task_func: 任务函数

        Raises:
            Exception: 任务执行失败时抛出
        """
        task_logger = self._get_task_logger(task_type)
        try:
            task_logger.info(f"开始执行{task_type}任务")
            start_time = time.time()

            # 执行任务
            task_func()

            # 记录成功
            duration = time.time() - start_time
            task_logger.success(f"{task_type}任务执行成功，耗时: {duration:.2f}秒")
            self._update_task_history(task_type, "success")

        except Exception as e:
            # 记录失败
            error_msg = str(e)
            task_logger.error(f"{task_type}任务执行失败: {error_msg}")
            self._update_task_history(task_type, "failed", error_msg)

            # 记录详细的异常信息
            task_logger.error(f"异常详情: {traceback.format_exc()}")

    def start(self) -> bool:
        """
        启动调度器守护进程

        Returns:
            bool: 是否启动成功
        """
        try:
            # 检查是否已经在运行
            if self.is_running():
                logger.warning("调度器已经在运行中")
                return True

            logger.info("正在启动调度器...")

            def handle_signal(signum, frame):
                self.running = False

            # 设置信号处理
            signal.signal(signal.SIGTERM, handle_signal)
            signal.signal(signal.SIGINT, handle_signal)

            # 创建守护进程上下文
            context = daemon.DaemonContext(
                working_directory=str(self.project_dir),
                umask=0o002,
                pidfile=daemon.pidfile.PIDLockFile(str(self.pid_file)),
            )

            with context:
                # 记录PID
                with open(self.pid_file, "w") as f:
                    f.write(str(os.getpid()))

                # 设置日志
                logger.add(str(self.log_file), rotation="1 day", retention="30 days")

                logger.info("调度器守护进程已启动")
                self._update_status("running")

                # 运行调度器
                self.running = True
                while self.running:
                    try:
                        # 获取待执行的任务
                        jobs = schedule.jobs
                        for job in jobs:
                            # 如果任务应该执行
                            if job.should_run:
                                # 获取任务类型
                                task_type = getattr(job, "task_type", None)
                                if task_type:
                                    # 包装任务函数
                                    original_func = job.job_func
                                    self._run_task_with_logging(task_type, original_func)

                                # 运行任务
                                job.run()

                                # 更新下次执行时间
                                if task_type:
                                    next_run = (
                                        job.next_run.strftime("%Y-%m-%d %H:%M:%S")
                                        if job.next_run
                                        else None
                                    )
                                    self._update_status(
                                        task_info={task_type: {"next_run": next_run}}
                                    )

                    except Exception as e:
                        logger.error(f"调度器执行出错: {e}")

                    time.sleep(1)

                logger.info("调度器守护进程已停止")
                self._update_status("stopped")

            return True

        except Exception as e:
            logger.error(f"启动调度器守护进程失败: {e}")
            return False

    def stop(self) -> bool:
        """
        停止调度器守护进程

        Returns:
            bool: 是否停止成功
        """
        try:
            if not self.is_running():
                logger.warning("调度器未在运行")
                return True

            # 读取PID
            with open(self.pid_file, "r") as f:
                pid = int(f.read().strip())

            # 发送终止信号
            os.kill(pid, signal.SIGTERM)

            # 等待进程结束
            max_wait = 10
            while max_wait > 0 and self.is_running():
                time.sleep(1)
                max_wait -= 1

            # 如果进程仍在运行，强制终止
            if self.is_running():
                os.kill(pid, signal.SIGKILL)
                self._update_status("stopped")

            # 删除PID文件
            if self.pid_file.exists():
                self.pid_file.unlink()

            logger.success("调度器已停止")
            return True

        except Exception as e:
            logger.error(f"停止调度器失败: {e}")
            return False

    def is_running(self) -> bool:
        """
        检查调度器是否正在运行

        Returns:
            bool: 是否正在运行
        """
        if not self.pid_file.exists():
            return False

        try:
            with open(self.pid_file, "r") as f:
                pid = int(f.read().strip())

            # 检查进程是否存在
            os.kill(pid, 0)
            return True
        except (FileNotFoundError, ValueError, ProcessLookupError):
            return False
        except PermissionError:
            return True

    def get_status(self) -> SchedulerStatus:
        """
        获取调度器状态

        Returns:
            SchedulerStatus: 调度器状态信息

        Raises:
            Exception: 获取状态失败时抛出
        """
        try:
            if self.status_file.exists():
                with open(self.status_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"获取调度器状态失败: {e}")
            return {}

    def get_logs(self, task_type: Optional[str] = None, lines: int = 100) -> str:
        """
        获取调度器或任务日志

        Args:
            task_type: 任务类型，为None时获取调度器日志
            lines: 返回的日志行数

        Returns:
            str: 日志内容

        Raises:
            Exception: 获取日志失败时抛出
        """
        try:
            if task_type:
                log_file = self.tasks_dir / task_type / "latest.log"
            else:
                log_file = self.log_file

            if not log_file.exists():
                return "日志文件不存在"

            # 读取最后N行日志
            output = check_output(["tail", "-n", str(lines), str(log_file)])
            return output.decode("utf-8")

        except Exception as e:
            logger.error(f"获取日志失败: {e}")
            return f"获取日志失败: {e}"

    def restart(self) -> bool:
        """
        重启调度器守护进程

        Returns:
            bool: 是否重启成功
        """
        self.stop()
        return self.start()

    def run_task(self, task_type: str, job_id: str) -> bool:
        """
        立即执行指定任务

        Args:
            task_type: 任务类型
            job_id: 任务ID

        Returns:
            bool: 是否执行成功

        Raises:
            Exception: 执行任务失败时抛出
        """
        try:
            # 检查调度器是否在运行
            if not self.is_running():
                logger.error("调度器未运行")
                return False

            # 查找对应的任务
            found_job = None
            for job in schedule.jobs:
                if getattr(job, "job_id", None) == job_id:
                    found_job = job
                    break

            if not found_job:
                logger.error(f"未找到ID为 {job_id} 的任务")
                return False

            # 获取任务函数
            job_func = found_job.job_func

            # 执行任务并记录日志
            self._run_task_with_logging(task_type, job_func)

            return True

        except Exception as e:
            logger.error(f"执行任务失败: {e}")
            return False
