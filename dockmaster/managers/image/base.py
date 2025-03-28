"""镜像管理基础类型定义"""

from datetime import datetime
from typing import Dict, List, TypedDict


class ImageBuildError(Exception):
    """镜像构建错误"""
    pass


class ImagePushError(Exception):
    """镜像推送错误"""
    pass


class ProjectImage(TypedDict):
    """项目镜像信息类型"""
    id: str
    tag: str
    full_tag: str
    created: str
    created_time: datetime
    size_mb: float
    created_ago: int


class ImagesSummary(TypedDict):
    """镜像摘要信息类型"""
    total_count: int
    total_size: float
    actual_disk_usage: float
    repos: Dict[str, int]
    project_images: List[ProjectImage] 