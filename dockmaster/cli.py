"""CLI命令行接口模块"""

import sys
import os
import typer
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime

from loguru import logger
from dockmaster.constants import (
    DEFAULT_FILES,
    DEFAULT_PROJECT_CONFIG,
    REQUIRED_FILES,
    PROJECT_NAME_PATTERN,
    INVALID_PROJECT_NAME_CHARS,
    ERROR_MESSAGES,
    COLORS
)
from dockmaster.interactive import configure_project, configure_schedule
from dockmaster.utils import confirm_action
from dockmaster.cli_utils import check_project_status, ProjectContext, get_project_manager
from dockmaster.managers.project_manager import ProjectManager

# 创建CLI应用
app = typer.Typer(
    help="Docker项目管理工具",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich"
)

@app.command("init")
def init_project(
    project_dir: str = typer.Argument(None, help="项目目录路径"),
    name: str = typer.Option(None, "-n", "--name", help="项目名称"),
    force: bool = typer.Option(False, "-f", "--force", help="强制初始化，即使缺少必需文件")
):
    """初始化新项目"""
    try:
        ctx = ProjectContext.get_instance()
        ctx.project_dir = project_dir
        ctx.project_name = name
        
        # 检查必需文件
        current_dir = ctx.project_dir
        missing_files = []
        
        for required_file in REQUIRED_FILES:
            if not os.path.exists(os.path.join(current_dir, required_file)):
                missing_files.append(required_file)
        
        if missing_files and not force:
            logger.warning("警告：以下必需文件不存在：")
            for file in missing_files:
                logger.warning(f"  - {file}")
            logger.warning("\n您可以：")
            logger.warning("1. 创建这些文件后再初始化")
            logger.warning("2. 使用 --force 参数强制初始化")
            sys.exit(1)
        
        project_manager = get_project_manager()
        if project_manager.create_project(ctx.project_dir):
            logger.success(f"项目 '{ctx.project_name}' 创建成功")
            
            # 如果是强制初始化，显示提醒
            if force and missing_files:
                logger.warning("\n注意：以下文件仍然缺失：")
                for file in missing_files:
                    logger.warning(f"  - {file}")
                logger.warning("请确保在使用其他命令前创建这些文件")
        else:
            logger.error("项目创建失败")
            sys.exit(1)
    except Exception as e:
        logger.error(f"错误：{str(e)}")
        sys.exit(1)

@app.command("config")
def config_project():
    """交互式配置项目基本信息"""
    try:
        project_manager = get_project_manager()
        
        # 获取当前配置
        current_config = project_manager.get_config()
        
        # 如果配置为空，创建默认配置结构
        if not current_config:
            current_config = project_manager.create_default_config()
        
        # 使用交互式配置模块获取用户输入的基本配置
        # 注意：这里只会更新用户交互式配置的几个基本项
        updated_fields = configure_project(current_config)
        
        # 只更新用户交互式配置的那几个项
        config_updates = {
            'project': {'name': updated_fields['project']['name']},
            'image': {
                'name': updated_fields['image']['name'],
                'registry': {
                    'url': updated_fields['image']['registry']['url'],
                    'username': updated_fields['image']['registry']['username']
                }
            },
            'container': {'name': updated_fields['container']['name']}
        }
        
        # 保存配置
        if project_manager.update_config(config_updates):
            logger.success("配置更新成功")
        else:
            logger.error("配置更新失败")
            sys.exit(1)
    except Exception as e:
        logger.error(f"配置更新失败: {str(e)}")
        sys.exit(1)

@app.command("build")
def build_image(
    dockerfile: str = typer.Option(None, "-f", "--file", help="Dockerfile路径"),
    push: bool = typer.Option(False, "-p", "--push", help="构建后推送镜像"),
    build_args: list[str] = typer.Option([], "--build-arg", help="构建参数，格式：KEY=VALUE", callback=lambda x: x or []),
    force: bool = typer.Option(False, "-f", "--force", help="强制构建，不进行状态检查")
):
    """构建Docker镜像"""
    try:
        project_manager = get_project_manager()
        
        # 状态检查
        if not force and not check_project_status(project_manager, 'build'):
            return
        
        # 自动查找Dockerfile
        if not dockerfile:
            dockerfile = os.path.join(project_manager.project_dir, DEFAULT_FILES['dockerfile'])
        
        # 处理构建参数
        build_args_dict = {}
        for arg in build_args:
            try:
                key, value = arg.split('=', 1)
                build_args_dict[key.strip()] = value.strip()
            except ValueError:
                logger.warning(f"警告：忽略无效的构建参数 '{arg}'，正确格式为 KEY=VALUE")
        
        if project_manager.image_manager.build_image(dockerfile, build_args_dict):
            logger.success("镜像构建成功")
            if push and project_manager.image_manager.push_image():
                logger.success("镜像推送成功")
        else:
            logger.error("镜像构建失败")
            sys.exit(1)
    except Exception as e:
        logger.error(f"错误：{str(e)}")
        sys.exit(1)

@app.command("up")
def start_container(
    compose_file: str = typer.Option(None, "-f", "--file", help="Docker Compose文件路径"),
    force: bool = typer.Option(False, "-f", "--force", help="强制启动，不进行状态检查")
):
    """启动容器"""
    try:
        project_manager = get_project_manager()
        
        # 状态检查
        if not force and not check_project_status(project_manager, 'up'):
            return
        
        # 自动查找docker-compose.yml
        if not compose_file:
            compose_file = os.path.join(project_manager.project_dir, DEFAULT_FILES['compose_file'])
        
        if project_manager.container_manager.start_container(compose_file):
            logger.success("容器启动成功")
        else:
            logger.error("容器启动失败")
            sys.exit(1)
    except Exception as e:
        logger.error(f"错误：{str(e)}")
        sys.exit(1)

@app.command("down")
def stop_container(
    force: bool = typer.Option(False, "-f", "--force", help="强制停止，不进行状态检查")
):
    """停止容器"""
    try:
        project_manager = get_project_manager()
        
        # 状态检查
        if not force and not check_project_status(project_manager, 'down'):
            return
        
        if project_manager.container_manager.stop_container():
            logger.success("容器已停止")
        else:
            logger.error("停止容器失败")
            sys.exit(1)
    except Exception as e:
        logger.error(f"错误：{str(e)}")
        sys.exit(1)

@app.command("save")
def save_container(
    tag: str = typer.Option(None, "-t", "--tag", help="镜像标签"),
    cleanup: bool = typer.Option(False, "-c", "--cleanup", help="保存前清理容器"),
    force: bool = typer.Option(False, "-f", "--force", help="强制保存，不进行状态检查")
):
    """保存容器为镜像"""
    try:
        project_manager = get_project_manager()
        
        # 状态检查
        if not force and not check_project_status(project_manager, 'save'):
            return
        
        # 获取容器名称作为镜像名称
        container_name = project_manager.config.get('container', {}).get('name')
        
        # 自动生成标签
        if not tag:
            tag = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 构建完整的镜像名称（repository:tag格式）
        image_name = f"{container_name}:{tag}" if container_name else tag
        
        if project_manager.container_manager.save_as_image(image_name, cleanup):
            logger.success(f"容器已保存为镜像 {image_name}")
        else:
            logger.error("保存容器失败")
            sys.exit(1)
    except Exception as e:
        logger.error(f"错误：{str(e)}")
        sys.exit(1)

@app.command("push")
def push_image(
    registry: str = typer.Option(None, "-r", "--registry", help="远程仓库地址"),
    username: str = typer.Option(None, "-u", "--username", help="仓库用户名"),
    password: str = typer.Option(None, "-p", "--password", help="仓库密码"),
    tag: str = typer.Option("latest", "-t", "--tag", help="要推送的镜像标签"),
    force: bool = typer.Option(False, "-f", "--force", help="强制推送，不进行状态检查")
):
    """推送镜像到远程仓库"""
    try:
        project_manager = get_project_manager()
        
        # 状态检查
        if not force and not check_project_status(project_manager, 'push'):
            return
        
        # 如果未指定，则使用配置中的值
        if not registry:
            registry = project_manager.config.get('image', {}).get('registry', {}).get('url')
        
        if not username:
            username = project_manager.config.get('image', {}).get('registry', {}).get('username')
            if not username:
                logger.warning("未指定用户名，推送可能会失败")
                logger.warning("Docker Hub要求镜像名称格式为 '用户名/镜像名'")
                username = typer.prompt("请输入仓库用户名", default="")
        
        if not password:
            # 尝试从环境变量获取密码
            if username:
                env_var_name = f"DOCKER_PASSWORD_{username.upper()}"
                password = os.environ.get(env_var_name)
                if password:
                    logger.info(f"已从环境变量 {env_var_name} 获取密码")
            
            # 如果用户特定环境变量没有密码，尝试通用环境变量
            if not password:
                password = os.environ.get("DOCKER_PASSWORD")
                if password:
                    logger.info("已从环境变量 DOCKER_PASSWORD 获取密码")
            
            # 如果环境变量中没有密码，尝试配置文件
            if not password:
                password = project_manager.config.get('image', {}).get('registry', {}).get('password')
            
            # 如果仍然没有密码，提示用户输入
            if not password and username:
                logger.warning("未找到密码，您可以：")
                logger.warning(f"1. 设置环境变量 {env_var_name if username else 'DOCKER_PASSWORD'}")
                logger.warning("2. 在配置文件中设置密码")
                logger.warning("3. 使用 'docker login' 命令手动登录")
                logger.warning("4. 现在输入密码（不推荐，会显示在命令历史中）")
                logger.warning("5. 如果您已经使用过 'docker login'，可以直接按回车输入空密码")
                password = typer.prompt("请输入仓库密码", default="", hide_input=True)
                # 如果用户输入了空密码，表示使用 docker login 的凭证
                if password == "":
                    logger.info("使用 docker login 的凭证进行推送")
                    password = None
        
        # 推送镜像
        if project_manager.image_manager.push_image(registry, username, password):
            logger.success(f"镜像推送成功")
        else:
            logger.error("推送镜像失败")
            sys.exit(1)
    except Exception as e:
        logger.error(f"错误：{str(e)}")
        sys.exit(1)

@app.command("schedule")
def schedule_task(
    task_type: str = typer.Argument(None, help="任务类型：backup/cleanup/list/remove"),
    cron: str = typer.Argument(None, help="时间格式 (HH:MM)，仅用于命令行方式"),
    force: bool = typer.Option(False, "-f", "--force", help="强制设置，不进行状态检查"),
):
    """配置定时任务"""
    try:
        project_manager = get_project_manager()
        
        # 列出所有定时任务
        if task_type == "list":
            tasks = project_manager.container_manager.list_scheduled_tasks()
            if not tasks:
                logger.info("当前没有配置定时任务")
                return
                
            logger.info("当前配置的定时任务:")
            for task_name, task_info in tasks.items():
                logger.info(f"- {task_name}: {task_info['cron']}")
                for key, value in task_info.items():
                    if key not in ['cron', 'job_id']:
                        logger.info(f"  {key}: {value}")
            return
            
        # 删除定时任务
        if task_type == "remove":
            if not cron:
                # 如果没有指定要删除的任务类型，使用交互式选择
                tasks = project_manager.container_manager.list_scheduled_tasks()
                if not tasks:
                    logger.info("当前没有配置定时任务")
                    return
                    
                from dockmaster.interactive import questionary
                task_to_remove = questionary.select(
                    "选择要删除的任务",
                    choices=list(tasks.keys())
                ).ask()
                
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
            return
        
        # 对于备份任务，需要检查容器状态
        if not force and task_type == "backup":
            if not check_project_status(project_manager, 'save'):
                logger.error("容器未运行，无法设置备份任务")
                return
        
        if not task_type or not cron:
            # 使用交互式配置模块
            config = configure_schedule()
            task_type = config["type"]
            schedule_config = config["schedule"]
            
            # 再次检查，因为用户可能在交互式配置中选择了备份任务
            if not force and task_type == "backup":
                if not check_project_status(project_manager, 'save'):
                    logger.error("容器未运行，无法设置备份任务")
                    return
            
            if task_type == "backup":
                if project_manager.container_manager.schedule_backup(
                    schedule_config, None, config["cleanup"], config["auto_push"]
                ):
                    logger.success(f"已设置备份任务: {schedule_config}")
                else:
                    logger.error("设置备份任务失败")
                    sys.exit(1)
            elif task_type == "cleanup":
                if project_manager.container_manager.schedule_cleanup(schedule_config, config["paths"]):
                    logger.success(f"已设置清理任务: {schedule_config}")
                else:
                    logger.error("设置清理任务失败")
                    sys.exit(1)
        else:
            # 命令行参数方式 - 使用简单的每日定时格式
            # 创建一个简单的每日定时配置
            schedule_config = {
                "type": "daily",
                "time": cron
            }
            
            if task_type == "backup":
                if project_manager.container_manager.schedule_backup(schedule_config):
                    logger.success(f"已设置备份任务: 每天 {cron}")
                else:
                    logger.error("设置备份任务失败")
                    sys.exit(1)
            elif task_type == "cleanup":
                if project_manager.container_manager.schedule_cleanup(schedule_config):
                    logger.success(f"已设置清理任务: 每天 {cron}")
                else:
                    logger.error("设置清理任务失败")
                    sys.exit(1)
    except Exception as e:
        logger.error(f"错误：{str(e)}")
        sys.exit(1)

@app.command("status")
def show_status():
    """显示项目状态"""
    try:
        project_manager = get_project_manager()
        status = project_manager.get_status()
        
        logger.info("\n项目信息:")
        logger.info(f"  名称: {status['project']['name']}")
        logger.info(f"  目录: {status['project']['directory']}")
        
        logger.info("\n镜像信息:")
        logger.info(f"  名称: {status['image']['name']}")
        logger.info(f"  仓库: {status['image']['registry']['url']}")
        
        logger.info("\n容器信息:")
        logger.info(f"  名称: {status['container']['name']}")
        logger.info(f"  状态: {status['container']['status']}")
        
        logger.info("\n定时任务:")
        if status['schedules']:
            for task in status['schedules']:
                logger.info(f"  - {task['type']}: {task['schedule']}")
        else:
            logger.info("  无定时任务")
    except Exception as e:
        logger.error(f"错误：{str(e)}")
        sys.exit(1)

@app.command("logs")
def show_logs(
    follow: bool = typer.Option(False, "-f", "--follow", help="持续显示日志"),
    force: bool = typer.Option(False, "--force", help="强制显示日志，不进行状态检查")
):
    """查看容器日志"""
    try:
        project_manager = get_project_manager()
        
        # 状态检查
        if not force and not check_project_status(project_manager, 'logs'):
            return
            
        project_manager.container_manager.show_logs(follow)
    except Exception as e:
        logger.error(f"错误：{str(e)}")
        sys.exit(1)

@app.command("cleanup")
def cleanup_images(
    days: int = typer.Option(None, "-d", "--days", help="保留最近几天的镜像"),
    count: int = typer.Option(None, "-n", "--count", help="为每个仓库保留的最新镜像数量"),
    keep_latest: bool = typer.Option(True, "-l", "--keep-latest/--no-keep-latest", help="是否保留latest标签的镜像"),
    dry_run: bool = typer.Option(False, "--dry-run", help="只显示将要删除的镜像，不实际删除"),
    interactive: bool = typer.Option(True, "-i/--no-interactive", help="是否使用交互式模式")
):
    """清理历史镜像"""
    try:
        project_manager = get_project_manager()
        
        # 如果没有指定参数且使用交互式模式
        if interactive and days is None and count is None:
            # 获取镜像摘要信息
            image_summary = project_manager.image_manager.get_images_summary()
            
            # 交互式配置
            from dockmaster.interactive import configure_cleanup
            cleanup_config = configure_cleanup(image_summary)
            
            # 如果用户取消，则退出
            if cleanup_config.get('cancel', False):
                logger.info("已取消清理操作")
                return
            
            # 更新参数
            days = cleanup_config.get('days')
            count = cleanup_config.get('count')
            keep_latest = cleanup_config.get('keep_latest', True)
            dry_run = cleanup_config.get('dry_run', False)
        elif days is None and count is None:
            logger.error("错误：必须指定--days或--count参数，或使用交互式模式")
            logger.info("提示：运行 'dm cleanup' 不带参数将启动交互式模式")
            sys.exit(1)
            
        # 执行清理
        to_delete, to_keep = project_manager.image_manager.cleanup_images(
            keep_latest=keep_latest,
            keep_days=days,
            keep_count=count,
            dry_run=dry_run
        )
        
        # 显示结果
        if dry_run:
            logger.warning("模拟运行模式，不会实际删除镜像")
            
        if to_delete:
            logger.warning("将删除以下镜像:")
            for image in to_delete:
                logger.warning(f"  - {image}")
        else:
            logger.success("没有符合条件的镜像需要删除")
            
        if to_keep:
            logger.success("将保留以下镜像:")
            for image in to_keep:
                logger.success(f"  - {image}")
                
        # 如果不是dry run，显示删除结果
        if not dry_run and to_delete:
            logger.success(f"已成功删除 {len(to_delete)} 个镜像")
            
    except Exception as e:
        logger.error(f"错误：{str(e)}")
        sys.exit(1)

def main():
    """主入口函数"""
    app()

if __name__ == "__main__":
    main() 