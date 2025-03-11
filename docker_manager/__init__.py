"""Docker项目管理工具包"""

# 导入loguru并配置logger
from loguru import logger
from typing import Dict, Any

# 移除默认处理器
logger.remove()
# 添加标准输出处理器
logger.add(
    sink=lambda msg: print(msg, end=""),  # 使用标准输出
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    colorize=True,
    level="INFO"
)

# 导入其他模块
from .cli import main, app

__version__ = '0.1.0'

__all__ = [
    'logger',
]