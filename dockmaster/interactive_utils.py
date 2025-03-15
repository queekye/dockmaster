"""交互式工具函数模块"""

import typer
from loguru import logger


def confirm_action(message: str = "确认执行此操作?", default: bool = True) -> bool:
    """
    请求用户确认操作

    Args:
        message: 提示消息
        default: 默认选项

    Returns:
        bool: 用户是否确认
    """
    try:
        return typer.confirm(message, default=default)
    except (KeyboardInterrupt, EOFError):
        logger.warning("\n操作已取消")
        return False 