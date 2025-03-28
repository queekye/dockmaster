"""镜像清理相关功能"""

import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Protocol, Tuple, TypedDict, cast

from loguru import logger

from .base import ImageBuildError
from .utils import parse_image_name


class CleanupStrategy(Protocol):
    """清理策略协议"""

    def filter_images(
        self, repo_images: List[Dict], latest_image_id: Optional[str]
    ) -> Tuple[List[str], List[str]]:
        """筛选要删除和保留的镜像"""
        ...


class TimeBasedCleanupStrategy:
    """基于时间的清理策略"""

    def __init__(self, keep_days: int):
        """
        初始化时间清理策略

        Args:
            keep_days: 保留最近几天的镜像
        """
        self.keep_days = keep_days

    def filter_images(
        self, repo_images: List[Dict], latest_image_id: Optional[str]
    ) -> Tuple[List[str], List[str]]:
        """
        筛选要删除和保留的镜像

        Args:
            repo_images: 仓库镜像列表
            latest_image_id: latest标签的镜像ID，如果需要保留

        Returns:
            Tuple[List[str], List[str]]: (要删除的镜像, 要保留的镜像)
        """
        to_delete = []
        to_keep = []
        
        # 计算截止日期
        cutoff_date = datetime.now() - timedelta(days=self.keep_days)
        cutoff_date_str = cutoff_date.strftime("%Y-%m-%dT%H:%M:%S")

        for img in repo_images:
            # 如果是latest且需要保留，则跳过
            if latest_image_id and img["id"] == latest_image_id:
                continue

            # 检查是否是时间戳格式的标签
            if re.match(r"^\d{8}_\d{6}$", img["tag"]):
                if img["created"] < cutoff_date_str:
                    to_delete.append(img["full_tag"])
                else:
                    to_keep.append(img["full_tag"])
        
        return to_delete, to_keep


class CountBasedCleanupStrategy:
    """基于数量的清理策略"""

    def __init__(self, keep_count: int):
        """
        初始化数量清理策略

        Args:
            keep_count: 为每个仓库保留的最新镜像数量
        """
        self.keep_count = keep_count

    def filter_images(
        self, repo_images: List[Dict], latest_image_id: Optional[str]
    ) -> Tuple[List[str], List[str]]:
        """
        筛选要删除和保留的镜像

        Args:
            repo_images: 仓库镜像列表
            latest_image_id: latest标签的镜像ID，如果需要保留

        Returns:
            Tuple[List[str], List[str]]: (要删除的镜像, 要保留的镜像)
        """
        to_delete = []
        to_keep = []
        
        # 过滤出时间戳格式的标签
        timestamp_images = [
            img for img in repo_images if re.match(r"^\d{8}_\d{6}$", img["tag"])
        ]

        # 保留指定数量的最新镜像
        for i, img in enumerate(timestamp_images):
            # 如果是latest且需要保留，则跳过
            if latest_image_id and img["id"] == latest_image_id:
                continue

            if i < self.keep_count:
                to_keep.append(img["full_tag"])
            else:
                to_delete.append(img["full_tag"])
        
        return to_delete, to_keep


class ImageCleaner:
    """镜像清理器类"""

    def __init__(self, docker_client, image_name: str):
        """
        初始化镜像清理器

        Args:
            docker_client: Docker客户端实例
            image_name: 镜像名称
        """
        self.docker_client = docker_client
        self.image_name = image_name

    def cleanup(
        self,
        keep_latest: bool = True,
        keep_days: Optional[int] = None,
        keep_count: Optional[int] = None,
        dry_run: bool = False,
    ) -> Tuple[List[str], List[str]]:
        """
        清理旧镜像

        Args:
            keep_latest: 是否保留latest标签的镜像
            keep_days: 保留最近几天的镜像
            keep_count: 为每个仓库保留的最新镜像数量
            dry_run: 是否只显示将要删除的镜像，不实际删除

        Returns:
            Tuple[List[str], List[str]]: (已删除的镜像ID列表, 保留的镜像ID列表)

        Raises:
            ImageBuildError: 清理失败时抛出
        """
        try:
            # 创建清理策略
            strategy = None
            if keep_days is not None:
                strategy = TimeBasedCleanupStrategy(keep_days)
            elif keep_count is not None:
                strategy = CountBasedCleanupStrategy(keep_count)
            else:
                # 如果没有提供策略，默认保留所有镜像
                logger.warning("未指定清理策略，将保留所有镜像")
                return [], []

            # 获取所有镜像
            all_images = self.docker_client.images.list()

            # 按仓库分组
            repo_images = self._group_images_by_repo(all_images)

            # 分析需要删除的镜像
            to_delete, to_keep = self._analyze_images_to_delete(
                repo_images, keep_latest, strategy
            )

            # 如果是dry run，只返回结果不删除
            if dry_run:
                return to_delete, to_keep

            # 执行删除
            deleted = self._delete_images(to_delete)

            return deleted, to_keep

        except Exception as e:
            logger.error(f"清理镜像失败: {e}")
            return [], []

    def _group_images_by_repo(
        self, all_images: List
    ) -> Dict[str, List[Dict]]:
        """
        按仓库名分组镜像

        Args:
            all_images: 所有镜像列表

        Returns:
            Dict[str, List[Dict]]: 按仓库分组的镜像
        """
        repo_images = {}
        for image in all_images:
            for tag in image.tags:
                if ":" in tag:
                    repo, tag_name = tag.split(":", 1)
                    if repo not in repo_images:
                        repo_images[repo] = []
                    repo_images[repo].append(
                        {
                            "id": image.id,
                            "tag": tag_name,
                            "full_tag": tag,
                            "created": image.attrs["Created"],
                        }
                    )
        
        # 对每个仓库的镜像按创建时间排序
        for repo in repo_images:
            repo_images[repo].sort(key=lambda x: x["created"], reverse=True)
        
        return repo_images

    def _analyze_images_to_delete(
        self,
        repo_images: Dict[str, List[Dict]],
        keep_latest: bool,
        strategy: CleanupStrategy,
    ) -> Tuple[List[str], List[str]]:
        """
        分析需要删除的镜像

        Args:
            repo_images: 按仓库分组的镜像
            keep_latest: 是否保留latest标签的镜像
            strategy: 清理策略

        Returns:
            Tuple[List[str], List[str]]: (要删除的镜像, 要保留的镜像)
        """
        to_delete = []
        to_keep = []

        # 处理每个仓库的镜像
        for repo, images in repo_images.items():
            # 如果不是当前项目的镜像，跳过
            base_image_name, _ = parse_image_name(self.image_name)
            if not repo.startswith(base_image_name):
                continue

            # 标记要保留的latest镜像
            latest_image_id = None
            if keep_latest:
                for img in images:
                    if img["tag"] == "latest":
                        latest_image_id = img["id"]
                        to_keep.append(img["full_tag"])
                        break

            # 应用清理策略
            delete_list, keep_list = strategy.filter_images(images, latest_image_id)
            to_delete.extend(delete_list)
            to_keep.extend(keep_list)

        return to_delete, to_keep

    def _delete_images(self, to_delete: List[str]) -> List[str]:
        """
        删除镜像

        Args:
            to_delete: 要删除的镜像列表

        Returns:
            List[str]: 已删除的镜像列表
        """
        deleted = []
        for tag in to_delete:
            try:
                self.docker_client.images.remove(tag)
                deleted.append(tag)
                logger.info(f"已删除镜像: {tag}")
            except Exception as e:
                logger.error(f"删除镜像 {tag} 失败: {e}")
        
        return deleted 