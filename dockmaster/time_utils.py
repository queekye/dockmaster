"""时间工具函数模块"""

from datetime import datetime


def get_timestamp() -> str:
    """
    获取当前时间戳，格式为YYYYMMDD_HHMMSS

    Returns:
        格式化的时间戳字符串
    """
    return datetime.now().strftime("%Y%m%d_%H%M%S") 