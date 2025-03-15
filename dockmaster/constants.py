"""常量配置模块"""

import os
from typing import Any, Dict, List, TypedDict, Optional

# 文件相关
class DefaultFiles(TypedDict):
    dockerfile: str
    compose_file: str
    config_file: str

DEFAULT_FILES: DefaultFiles = {
    "dockerfile": "Dockerfile",
    "compose_file": "docker-compose.yml",
    "config_file": "config.json",
}

# 项目默认配置
class RegistryConfig(TypedDict):
    url: str
    username: str
    password: str
    prefix: str

class ImageConfig(TypedDict):
    name: Optional[str]
    dockerfile: str
    registry: RegistryConfig

class ContainerBackupConfig(TypedDict):
    cleanup: bool
    auto_push: bool

class ContainerCleanupConfig(TypedDict):
    paths: List[str]

class ContainerConfig(TypedDict):
    name: Optional[str]
    compose_file: str
    cleanup: ContainerCleanupConfig
    backup: ContainerBackupConfig

class ProjectConfig(TypedDict):
    name: Optional[str]
    directory: Optional[str]

class DefaultProjectConfig(TypedDict):
    project: ProjectConfig
    image: ImageConfig
    container: ContainerConfig
    schedule: Dict[str, Any]

DEFAULT_PROJECT_CONFIG: DefaultProjectConfig = {
    "project": {"name": None, "directory": None},  # 将使用目录名  # 将使用当前目录
    "image": {
        "name": None,  # 将使用项目名
        "dockerfile": DEFAULT_FILES["dockerfile"],
        "registry": {
            "url": "docker.io",
            "username": "",
            "password": "",
            "prefix": "",  # 镜像前缀，优先于username
        },
    },
    "container": {
        "name": None,  # 将使用项目名
        "compose_file": DEFAULT_FILES["compose_file"],
        "cleanup": {"paths": ["/tmp/*", "/var/cache/*"]},
        "backup": {"cleanup": False, "auto_push": False},
    },
    "schedule": {
        # 定时任务配置
    },
}

# Docker相关配置
class DockerConfig(TypedDict):
    max_retries: int
    retry_delay: int
    startup_timeout: int

DOCKER_CONFIG: DockerConfig = {"max_retries": 3, "retry_delay": 2, "startup_timeout": 30}

# 文件检查配置
REQUIRED_FILES: List[str] = [DEFAULT_FILES["dockerfile"], DEFAULT_FILES["compose_file"]]

# 项目名称验证
PROJECT_NAME_PATTERN: str = r"^[a-zA-Z0-9_-]+$"
INVALID_PROJECT_NAME_CHARS: List[str] = ["..", "/", "\\"]

# 错误消息
class ErrorMessages(TypedDict):
    project_name_empty: str
    project_name_invalid: str
    project_name_illegal: str
    docker_connection: str
    file_not_found: str
    config_validation: str

ERROR_MESSAGES: ErrorMessages = {
    "project_name_empty": "项目名称不能为空",
    "project_name_invalid": "项目名称只能包含字母、数字、下划线和连字符",
    "project_name_illegal": "项目名称包含非法字符",
    "docker_connection": "无法连接到Docker守护进程: {}",
    "file_not_found": "{}不存在: {}",
    "config_validation": "配置验证失败: {}",
}

# 颜色配置
class Colors(TypedDict):
    success: str
    warning: str
    error: str
    info: str

COLORS: Colors = {"success": "green", "warning": "yellow", "error": "red", "info": "blue"}
