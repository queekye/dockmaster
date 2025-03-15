"""状态信息格式化模块"""

from typing import Any, Dict, List

from loguru import logger


def format_scheduler_status(status: Dict[str, Any], tasks: Dict[str, Any]) -> None:
    """格式化并显示调度器状态信息

    Args:
        status: 调度器状态信息
        tasks: 任务配置信息
    """
    # 显示调度器状态
    logger.info("\n调度器状态:")
    if status.get("status") == "running":
        logger.info(f"  状态: 运行中")
        if "uptime" in status:
            logger.info(f"  运行时间: {status['uptime']['formatted']}")
    else:
        logger.warning("  状态: 已停止")

    # 显示任务列表
    if not tasks:
        logger.info("\n当前没有配置定时任务")
        return

    logger.info("\n当前配置的定时任务:")
    for task_name, task_info in tasks.items():
        _format_task_info(task_name, task_info, status)


def format_project_status(status: Dict[str, Any]) -> None:
    """格式化并显示项目状态信息

    Args:
        status: 项目状态信息
    """
    logger.info("\n项目信息:")
    logger.info(f"  名称: {status['project']['name']}")
    logger.info(f"  目录: {status['project']['directory']}")

    _format_image_status(status["image"])
    _format_container_status(status["container"])
    _format_schedule_status(status["schedules"])


def _format_task_info(task_name: str, task_info: Dict[str, Any], status: Dict[str, Any]) -> None:
    """格式化单个任务的信息

    Args:
        task_name: 任务名称
        task_info: 任务配置信息
        status: 调度器状态信息
    """
    logger.info(f"\n- {task_name}:")
    logger.info(f"  调度: {task_info['cron']}")

    # 显示任务状态
    if "tasks" in status and task_name in status["tasks"]:
        task_status = status["tasks"][task_name]
        last_run = task_status.get("last_run", "从未执行")
        next_run = task_status.get("next_run", "未知")
        run_status = task_status.get("status", "未知")

        logger.info(f"  上次执行: {last_run}")
        if run_status == "success":
            logger.info(f"  执行状态: 成功")
        elif run_status == "failed":
            logger.warning(f"  执行状态: 失败")
            if "last_error" in task_status:
                logger.info(f"  错误信息: {task_status['last_error']}")
        logger.info(f"  下次执行: {next_run}")

    # 显示任务配置
    for key, value in task_info.items():
        if key not in ["cron", "job_id"]:
            logger.info(f"  {key}: {value}")


def _format_image_status(image_status: Dict[str, Any]) -> None:
    """格式化镜像状态信息

    Args:
        image_status: 镜像状态信息
    """
    logger.info("\n镜像信息:")
    logger.info(f"  名称: {image_status['name']}")
    logger.info(f"  仓库: {image_status['registry']['url']}")
    logger.info(f"  状态: {'存在' if image_status['exists'] else '不存在'}")
    logger.info(f"  备份数量: {image_status['backup_count']} 个")

    if image_status["backup_count"] > 0:
        logger.info(f"  总大小: {round(image_status['total_size_mb'], 2)} MB")
        logger.info(f"  最近备份: {image_status['latest_backup']} 天前")

        # 显示最近的几个备份镜像
        if image_status["summary"]["project_images"]:
            logger.info("  最近备份镜像:")
            for i, img in enumerate(
                image_status["summary"]["project_images"][:3]
            ):  # 只显示最近的3个
                logger.info(
                    f"    - {img['full_tag']} (创建于 {img['created_ago']} 天前, 大小 {img['size_mb']} MB)"
                )

            if len(image_status["summary"]["project_images"]) > 3:
                logger.info(
                    f"    ... 还有 {len(image_status['summary']['project_images']) - 3} 个备份镜像"
                )


def _format_container_status(container_status: Dict[str, Any]) -> None:
    """格式化容器状态信息

    Args:
        container_status: 容器状态信息
    """
    logger.info("\n容器信息:")
    logger.info(f"  名称: {container_status['name']}")
    logger.info(f"  状态: {container_status['status']}")


def _format_schedule_status(schedules: List[Dict[str, Any]]) -> None:
    """格式化调度任务状态信息

    Args:
        schedules: 调度任务列表
    """
    logger.info("\n定时任务:")
    if schedules:
        for task in schedules:
            logger.info(f"  - {task['type']}: {task['schedule']}")
    else:
        logger.info("  无定时任务")
