"""调度命令处理模块"""

import sys
import time
from typing import Optional

import typer
from loguru import logger

from ..cli_utils import check_project_status, get_project_manager
from ..formatters.status import format_scheduler_status
from ..interactive import configure_schedule, questionary


def handle_schedule_command(
    task_type: Optional[str],
    cron: Optional[str],
    force: bool = False,
    lines: int = 100,
    follow: bool = False,
    run_now: bool = False,
) -> None:
    """处理调度相关的命令

    Args:
        task_type: 任务类型：backup/cleanup/list/remove/start/stop/restart/logs
        cron: 时间格式 (HH:MM)，仅用于命令行方式
        force: 是否强制设置，不进行状态检查
        lines: 显示日志的行数
        follow: 是否持续显示日志
        run_now: 是否立即执行一次任务
    """
    try:
        project_manager = get_project_manager()

        # 调度器管理命令
        if task_type in ["start", "stop", "restart"]:
            if task_type == "start":
                if project_manager.container_manager.start_scheduler():
                    logger.success("调度器已启动")
                else:
                    logger.error("启动调度器失败")
                    sys.exit(1)
            elif task_type == "stop":
                if project_manager.container_manager.stop_scheduler():
                    logger.success("调度器已停止")
                else:
                    logger.error("停止调度器失败")
                    sys.exit(1)
            elif task_type == "restart":
                if project_manager.container_manager.restart_scheduler():
                    logger.success("调度器已重启")
                else:
                    logger.error("重启调度器失败")
                    sys.exit(1)
            return

        # 查看日志
        if task_type == "logs":
            # 如果指定了cron参数，作为任务类型
            task_log_type = cron if cron in ["backup", "cleanup"] else None

            if follow:
                # 持续显示日志
                last_position = 0
                while True:
                    logs = project_manager.container_manager.get_scheduler_logs(
                        task_log_type, lines
                    )
                    if len(logs) > last_position:
                        print(logs[last_position:], end="")
                        last_position = len(logs)
                    time.sleep(1)
            else:
                # 显示最近的日志
                logs = project_manager.container_manager.get_scheduler_logs(task_log_type, lines)
                print(logs)
            return

        # 列出所有定时任务
        if task_type == "list":
            tasks = project_manager.container_manager.list_scheduled_tasks()
            status = project_manager.container_manager.get_scheduler_status()
            format_scheduler_status(status, tasks)
            return

        # 删除定时任务
        if task_type == "remove":
            _handle_remove_task(project_manager, cron)
            return

        # 对于备份任务，需要检查容器状态
        if not force and task_type == "backup":
            if not check_project_status(project_manager, "save"):
                logger.error("容器未运行，无法设置备份任务")
                return

        if not task_type or not cron:
            _handle_interactive_schedule(project_manager, force, run_now)
        else:
            _handle_cli_schedule(project_manager, task_type, cron, run_now)

    except Exception as e:
        logger.error(f"错误：{str(e)}")
        sys.exit(1)


def _handle_remove_task(project_manager, cron: Optional[str]) -> None:
    """处理删除任务的逻辑"""
    if not cron:
        # 如果没有指定要删除的任务类型，使用交互式选择
        tasks = project_manager.container_manager.list_scheduled_tasks()
        if not tasks:
            logger.info("当前没有配置定时任务")
            return

        task_to_remove = questionary.select("选择要删除的任务", choices=list(tasks.keys())).ask()

        if project_manager.container_manager.remove_scheduled_task(task_to_remove):
            logger.success(f"已删除 {task_to_remove} 定时任务")
        else:
            logger.error(f"删除 {task_to_remove} 定时任务失败")
    else:
        # 使用命令行参数指定要删除的任务类型
        if project_manager.container_manager.remove_scheduled_task(cron):
            logger.success(f"已删除 {cron} 定时任务")
        else:
            logger.error(f"删除 {cron} 定时任务失败")


def _handle_interactive_schedule(project_manager, force: bool, run_now: bool) -> None:
    """处理交互式调度配置"""
    config = configure_schedule()
    task_type = config["type"]
    schedule_config = config["schedule"]

    # 再次检查，因为用户可能在交互式配置中选择了备份任务
    if not force and task_type == "backup":
        if not check_project_status(project_manager, "save"):
            logger.error("容器未运行，无法设置备份任务")
            return

    job_id = None
    if task_type == "backup":
        job_id = project_manager.container_manager.schedule_backup(
            schedule_config, None, config["cleanup"], config["auto_push"]
        )
        if job_id:
            logger.success(f"已设置备份任务: {schedule_config}")
    elif task_type == "cleanup":
        job_id = project_manager.container_manager.schedule_cleanup(
            schedule_config, config["paths"]
        )
        if job_id:
            logger.success(f"已设置清理任务: {schedule_config}")

    if not job_id:
        logger.error(f"设置{task_type}任务失败")
        sys.exit(1)

    # 如果用户选择立即启动调度器
    if job_id and config.get("start_scheduler", True):
        if not project_manager.container_manager.is_scheduler_running():
            if project_manager.container_manager.start_scheduler():
                logger.success("调度器已启动")
            else:
                logger.error("启动调度器失败")
                sys.exit(1)
        else:
            logger.info("调度器已经在运行中")

    # 在调度器启动后，如果需要立即执行任务
    if job_id and (run_now or config.get("run_now", False)):
        logger.info(f"正在通过调度器执行{task_type}任务...")
        if project_manager.container_manager.scheduler_daemon.run_task(task_type, job_id):
            logger.success(f"{task_type}任务已通过调度器执行")
        else:
            logger.error(f"通过调度器执行{task_type}任务失败")


def _handle_cli_schedule(project_manager, task_type: str, cron: str, run_now: bool) -> None:
    """处理命令行方式的调度配置"""
    # 创建一个简单的每日定时配置
    schedule_config = {"type": "daily", "time": cron}

    job_id = None
    if task_type == "backup":
        job_id = project_manager.container_manager.schedule_backup(schedule_config)
        if job_id:
            logger.success(f"已设置备份任务: 每天 {cron}")
    elif task_type == "cleanup":
        job_id = project_manager.container_manager.schedule_cleanup(schedule_config)
        if job_id:
            logger.success(f"已设置清理任务: 每天 {cron}")

    if not job_id:
        logger.error(f"设置{task_type}任务失败")
        sys.exit(1)

    # 命令行方式默认启动调度器
    if job_id and not project_manager.container_manager.is_scheduler_running():
        if project_manager.container_manager.start_scheduler():
            logger.success("调度器已启动")
        else:
            logger.error("启动调度器失败")
            sys.exit(1)

    # 在调度器启动后，如果需要立即执行任务
    if job_id and run_now:
        logger.info(f"正在通过调度器执行{task_type}任务...")
        if project_manager.container_manager.scheduler_daemon.run_task(task_type, job_id):
            logger.success(f"{task_type}任务已通过调度器执行")
        else:
            logger.error(f"通过调度器执行{task_type}任务失败")
