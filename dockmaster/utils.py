"""工具函数模块"""

import os
import re
import shlex
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional, Tuple, Union, TYPE_CHECKING

import docker
import typer
from loguru import logger

from .constants import DEFAULT_FILES, COLORS, ERROR_MESSAGES
from .interactive_utils import confirm_action

if TYPE_CHECKING:
    from .managers.project_manager import ProjectManager


def run_command(command: str, shell: bool = False, check: bool = True) -> Tuple[int, str, str]:
    """
    运行shell命令并返回结果

    Args:
        command: 要运行的命令
        shell: 是否使用shell执行
        check: 是否检查返回码

    Returns:
        (返回码, 标准输出, 标准错误)
    """
    logger.debug(f"执行命令: {command}")

    if shell:
        # 使用shell执行命令
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
    else:
        # 不使用shell执行命令
        args = shlex.split(command)
        process = subprocess.Popen(
            args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True
        )

    # 获取输出
    stdout, stderr = process.communicate()
    return_code = process.returncode

    # 检查返回码
    if check and return_code != 0:
        logger.error(f"命令执行失败: {command}")
        logger.error(f"错误输出: {stderr}")
        raise subprocess.CalledProcessError(return_code, command, stdout, stderr)

    return return_code, stdout, stderr


def create_temp_file(content: str) -> str:
    """
    创建临时文件并写入内容

    Args:
        content: 要写入的内容

    Returns:
        临时文件的路径
    """
    fd, path = tempfile.mkstemp(text=True)
    with os.fdopen(fd, "w") as f:
        f.write(content)
    return path


def check_project_status(project_manager: "ProjectManager", action: str) -> bool:
    """
    检查项目状态是否允许执行指定操作

    Args:
        project_manager: 项目管理器
        action: 操作名称

    Returns:
        bool: 是否允许执行操作
    """
    try:
        # 检查Docker连接
        try:
            project_manager.docker_client.ping()
        except Exception as e:
            logger.error(f"无法连接到Docker: {e}")
            logger.error("请确保Docker服务正在运行")
            return False

        # 根据操作类型进行检查
        if action == "build":
            # 检查Dockerfile是否存在
            dockerfile = os.path.join(project_manager.project_dir, DEFAULT_FILES["dockerfile"])
            if not os.path.exists(dockerfile):
                logger.error(f"Dockerfile不存在: {dockerfile}")
                logger.error("请创建Dockerfile或使用 -f 指定Dockerfile路径")
                return False

        elif action == "up":
            # 检查compose文件是否存在
            compose_file = os.path.join(project_manager.project_dir, DEFAULT_FILES["compose_file"])
            if not os.path.exists(compose_file):
                logger.error(f"Docker Compose文件不存在: {compose_file}")
                logger.error("请创建docker-compose.yml或使用 -f 指定Compose文件路径")
                return False

        elif action == "down":
            # 检查容器是否正在运行
            if not project_manager.container_manager.is_running():
                logger.warning("容器未运行，无需停止")
                return False

        elif action == "save":
            # 检查容器是否存在
            if not project_manager.container_manager.exists():
                logger.error("容器不存在，无法保存")
                logger.error("请先使用 'dm up' 启动容器")
                return False

        elif action == "push":
            # 检查镜像是否存在
            try:
                project_manager.docker_client.images.get(project_manager.image_manager.image_name)
            except docker.errors.ImageNotFound:
                logger.error(f"镜像 {project_manager.image_manager.image_name} 不存在")
                logger.error("请先使用 'dm build' 构建镜像")
                return False

            # 检查仓库配置
            registry = project_manager.config.get("image", {}).get("registry", {})
            if not registry.get("url"):
                logger.warning("未配置镜像仓库地址，将使用默认仓库 (docker.io)")

            if not registry.get("username"):
                logger.warning("未配置仓库用户名，可能无法推送到私有仓库")
                logger.warning("Docker Hub要求镜像名称格式为 '用户名/镜像名'")
                logger.warning("您可以在推送时使用 -u/--username 参数指定用户名")

            # 检查镜像名称格式
            image_name = project_manager.image_manager.image_name
            if "/" not in image_name and registry.get("username"):
                logger.info(f"将自动添加用户名 '{registry.get('username')}' 作为命名空间前缀")

        return True

    except Exception as e:
        logger.error(f"状态检查失败: {e}")
        return False
