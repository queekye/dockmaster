"""镜像管理工具函数"""

import re
from typing import Tuple, Union


def parse_image_name(image_name: str) -> Tuple[str, str]:
    """
    解析镜像名称，分离仓库名和标签

    Args:
        image_name: 镜像名称，格式为 "仓库名:标签"

    Returns:
        Tuple[str, str]: 仓库名和标签
    """
    if ":" in image_name:
        repository, tag = image_name.split(":", 1)
    else:
        repository = image_name
        tag = "latest"
    return repository, tag


def convert_size_to_mb(size_value: float, size_unit: str) -> float:
    """
    将不同单位的大小转换为MB

    Args:
        size_value: 大小数值
        size_unit: 单位（GB, MB, KB, B）

    Returns:
        float: 转换后的MB值
    """
    if "GB" in size_unit:
        return size_value * 1024
    elif "MB" in size_unit:
        return size_value
    elif "KB" in size_unit:
        return size_value / 1024
    elif "B" in size_unit and "GB" not in size_unit and "MB" not in size_unit and "KB" not in size_unit:
        return size_value / (1024 * 1024)
    else:
        return size_value


def parse_size_string(size_str: str) -> float:
    """
    解析大小字符串（例如：5.629GB）为MB

    Args:
        size_str: 大小字符串

    Returns:
        float: 转换后的MB值
    """
    match = re.match(r"([\d.]+)([a-zA-Z]+)", size_str)
    if match:
        size_value = float(match.group(1))
        size_unit = match.group(2)
        return convert_size_to_mb(size_value, size_unit)
    else:
        # 尝试直接解析为浮点数
        try:
            return float(size_str)
        except ValueError:
            return 0.0 