"""常量配置模块"""

import os
from typing import Dict, Any

# 文件相关
DEFAULT_FILES = {
    'dockerfile': 'Dockerfile',
    'compose_file': 'docker-compose.yml',
    'config_file': 'config.json'
}

# 项目默认配置
DEFAULT_PROJECT_CONFIG = {
    'project': {
        'name': None,  # 将使用目录名
        'directory': None  # 将使用当前目录
    },
    'image': {
        'name': None,  # 将使用项目名
        'dockerfile': DEFAULT_FILES['dockerfile'],
        'registry': {
            'url': 'docker.io',
            'username': '',
            'password': '',
            'prefix': ''  # 镜像前缀，优先于username
        }
    },
    'container': {
        'name': None,  # 将使用项目名
        'compose_file': DEFAULT_FILES['compose_file'],
        'cleanup': {
            'paths': ['/tmp/*', '/var/cache/*']
        },
        'backup': {
            'cleanup': False,
            'auto_push': False
        }
    },
    'schedule': {
        # 定时任务配置
    }
}

# Docker相关配置
DOCKER_CONFIG = {
    'max_retries': 3,
    'retry_delay': 2,
    'startup_timeout': 30
}

# 文件检查配置
REQUIRED_FILES = [
    DEFAULT_FILES['dockerfile'],
    DEFAULT_FILES['compose_file']
]

# 项目名称验证
PROJECT_NAME_PATTERN = r'^[a-zA-Z0-9_-]+$'
INVALID_PROJECT_NAME_CHARS = ['..', '/', '\\']

# 错误消息
ERROR_MESSAGES = {
    'project_name_empty': '项目名称不能为空',
    'project_name_invalid': '项目名称只能包含字母、数字、下划线和连字符',
    'project_name_illegal': '项目名称包含非法字符',
    'docker_connection': '无法连接到Docker守护进程: {}',
    'file_not_found': '{}不存在: {}',
    'config_validation': '配置验证失败: {}'
}

# 颜色配置
COLORS = {
    'success': 'green',
    'warning': 'yellow',
    'error': 'red',
    'info': 'blue'
} 