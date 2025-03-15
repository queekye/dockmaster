"""基础管理器类"""

from typing import Any, Dict, Optional

import docker
from docker.client import DockerClient
from loguru import logger


class BaseManager:
    """所有管理器类的基类，包含共享的属性和方法"""

    docker_client: DockerClient

    def __init__(self) -> None:
        """初始化基础管理器"""
        # 初始化Docker客户端
        try:
            self.docker_client = docker.from_env()
            logger.debug("Docker客户端初始化成功")
        except Exception as e:
            logger.error(f"Docker客户端初始化失败: {e}")
            raise

    def _check_docker_connection(self) -> bool:
        """
        检查Docker守护进程连接状态

        Returns:
            bool: 连接是否正常
        """
        try:
            self.docker_client.ping()
            return True
        except Exception as e:
            logger.error(f"Docker连接检查失败: {e}")
            return False
