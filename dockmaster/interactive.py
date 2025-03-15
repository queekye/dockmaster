"""交互式命令模块"""

from typing import Any, Dict, List

import questionary


def configure_project(config: Dict[str, Any]) -> Dict[str, Any]:
    """交互式配置项目基本信息

    注意：此函数只配置基本项目信息，如项目名称、镜像名称等。
    其他高级配置（如定时任务、备份等）请使用专门的命令或直接编辑配置文件。

    Args:
        config: 当前配置

    Returns:
        更新后的配置（仅包含用户交互式配置的项）
    """
    # 确保配置包含必要的结构
    if "project" not in config:
        config["project"] = {}
    if "image" not in config:
        config["image"] = {"registry": {}}
    if "container" not in config:
        config["container"] = {}
    if "registry" not in config["image"]:
        config["image"]["registry"] = {}

    # 创建一个新的配置字典，只包含要更新的项
    updated_config = {"project": {}, "image": {"registry": {}}, "container": {}}

    # 基本配置
    print("\n--- 基本项目配置 ---")
    print(
        "注意：此命令只配置基本项目信息。其他高级配置（如定时任务、备份等）请使用专门的命令或直接编辑配置文件。\n"
    )

    updated_config["project"]["name"] = questionary.text(
        "项目名称", default=config["project"].get("name", "")
    ).ask()

    # 镜像配置
    updated_config["image"]["name"] = questionary.text(
        "镜像名称", default=config["image"].get("name", "")
    ).ask()

    updated_config["image"]["registry"]["url"] = questionary.text(
        "镜像仓库地址", default=config["image"]["registry"].get("url", "docker.io")
    ).ask()

    updated_config["image"]["registry"]["prefix"] = questionary.text(
        "镜像前缀（可选，优先于用户名）", default=config["image"]["registry"].get("prefix", "")
    ).ask()

    updated_config["image"]["registry"]["username"] = questionary.text(
        "仓库用户名", default=config["image"]["registry"].get("username", "")
    ).ask()

    # 容器配置
    updated_config["container"]["name"] = questionary.text(
        "容器名称", default=config["container"].get("name", "")
    ).ask()

    return updated_config


def configure_cleanup(image_summary: Dict[str, Any]) -> Dict[str, Any]:
    """交互式配置镜像清理选项

    Args:
        image_summary: 镜像摘要信息，包含总数、仓库分组等

    Returns:
        清理配置选项
    """
    print("\n--- 镜像清理配置 ---")

    # 计算项目镜像的总大小
    project_images_size = sum(img["size_mb"] for img in image_summary["project_images"])
    project_images_count = len(image_summary["project_images"])

    print(
        f"当前项目共有 {project_images_count} 个镜像，占用空间约 {round(project_images_size, 2)} MB"
    )

    # 显示实际磁盘使用情况（如果可用）
    if image_summary.get("actual_disk_usage"):
        print(f"所有镜像实际占用磁盘空间约 {image_summary['actual_disk_usage']} MB（考虑层共享）")
        print(f"理论总大小约 {image_summary['total_size']} MB（不考虑层共享）")
        # 计算共享率
        if image_summary["total_size"] > 0:
            sharing_ratio = (
                (image_summary["total_size"] - image_summary["actual_disk_usage"])
                / image_summary["total_size"]
                * 100
            )
            print(f"层共享率约 {round(sharing_ratio, 2)}%")

    # 显示项目镜像详情
    if image_summary["project_images"]:
        print("\n项目镜像详情:")
        for i, img in enumerate(image_summary["project_images"]):
            print(
                f"  {i+1}. {img['full_tag']} - 创建于 {img['created_ago']} 天前，大小 {img['size_mb']} MB"
            )

    # 选择清理方式
    cleanup_method = questionary.select(
        "选择清理方式", choices=["按数量保留最新的镜像", "按时间保留最近的镜像", "取消"]
    ).ask()

    if cleanup_method == "取消":
        return {"cancel": True}

    # 是否保留latest标签
    keep_latest = questionary.confirm("是否保留latest标签的镜像?", default=True).ask()

    # 是否只是模拟运行
    dry_run = questionary.confirm("是否只模拟运行（不实际删除）?", default=False).ask()

    config = {"keep_latest": keep_latest, "dry_run": dry_run, "cancel": False}

    if cleanup_method == "按时间保留最近的镜像":
        days = questionary.text("保留最近几天的镜像?", default="7").ask()
        try:
            config["days"] = int(days)
        except ValueError:
            print("输入无效，使用默认值7")
            config["days"] = 7
        config["count"] = None

    elif cleanup_method == "按数量保留最新的镜像":
        count = questionary.text("为每个仓库保留的最新镜像数量?", default="5").ask()
        try:
            config["count"] = int(count)
        except ValueError:
            print("输入无效，使用默认值5")
            config["count"] = 5
        config["days"] = None

    return config


def configure_schedule() -> Dict[str, Any]:
    """交互式配置定时任务

    Returns:
        任务配置
    """
    task_type = questionary.select("选择任务类型", choices=["backup", "cleanup"]).ask()

    # 添加常用定时方案选择
    schedule_type = questionary.select(
        "选择执行频率", choices=["每天", "每周", "每月", "每小时"]
    ).ask()

    # 根据执行频率选择具体时间
    schedule_config = {}

    if schedule_type == "每天":
        time = questionary.text(
            "执行时间 (格式: HH:MM，例如: 00:00 表示午夜)", default="00:00"
        ).ask()
        schedule_config = {"type": "daily", "time": time}

    elif schedule_type == "每周":
        weekday = questionary.select(
            "选择星期几",
            choices=["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"],
        ).ask()

        weekday_map = {
            "星期一": "monday",
            "星期二": "tuesday",
            "星期三": "wednesday",
            "星期四": "thursday",
            "星期五": "friday",
            "星期六": "saturday",
            "星期日": "sunday",
        }

        time = questionary.text(
            "执行时间 (格式: HH:MM，例如: 00:00 表示午夜)", default="00:00"
        ).ask()

        schedule_config = {"type": "weekly", "weekday": weekday_map[weekday], "time": time}

    elif schedule_type == "每月":
        day = questionary.text("每月几号 (1-31)", default="1").ask()

        time = questionary.text(
            "执行时间 (格式: HH:MM，例如: 00:00 表示午夜)", default="00:00"
        ).ask()

        schedule_config = {"type": "monthly", "day": int(day), "time": time}

    elif schedule_type == "每小时":
        minute = questionary.text("每小时的第几分钟 (0-59)", default="0").ask()

        schedule_config = {"type": "hourly", "minute": int(minute)}

    config = {"type": task_type, "schedule": schedule_config}

    if task_type == "backup":
        config["cleanup"] = questionary.confirm("是否在备份前清理容器?", default=False).ask()

        config["auto_push"] = questionary.confirm("是否自动推送备份镜像?", default=False).ask()
    elif task_type == "cleanup":
        paths = questionary.text(
            "清理路径 (多个路径用逗号分隔)", default="/tmp/*,/var/cache/*"
        ).ask()
        config["paths"] = [p.strip() for p in paths.split(",")]

    # 添加启动调度器的选项
    config["start_scheduler"] = questionary.confirm("是否立即启动调度器?", default=True).ask()

    # 添加立即执行的选项
    config["run_now"] = questionary.confirm("是否立即执行一次任务?", default=False).ask()

    return config
