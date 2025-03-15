"""Docker项目管理工具包"""

# 导入loguru并配置logger
from typing import Any, Dict

from loguru import logger

# 移除默认处理器
logger.remove()
# 添加标准输出处理器
logger.add(
    sink=lambda msg: print(msg, end=""),  # 使用标准输出
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    colorize=True,
    level="INFO",
)

# 导入其他模块
from .cli import app, main

__version__ = "0.1.0"

__all__ = [
    "logger",
]
