"""镜像管理器类 - 门面模式实现"""

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from loguru import logger

from .base_manager import BaseManager
from .image.base import ImageBuildError, ImagePushError, ProjectImage, ImagesSummary
from .image.build import ImageBuilder
from .image.push import ImagePusher
from .image.tag import ImageTagger
from .image.cleanup import ImageCleaner
from .image.summary import ImageSummarizer


class ImageManager(BaseManager):
    """镜像管理器类，用于构建和推送镜像"""

    def __init__(self, project_dir: str, image_name: Optional[str] = None) -> None:
        """
        初始化镜像管理器

        Args:
            project_dir: 项目目录路径
            image_name: 镜像名称，可选
        """
        super().__init__()
        self.project_dir = Path(project_dir)
        self.image_name = image_name
        
        # 初始化子组件
        self.builder = ImageBuilder(self.docker_client, self.project_dir, self.image_name) if image_name else None
        self.pusher = ImagePusher(self.docker_client, self.image_name) if image_name else None
        self.tagger = ImageTagger(self.docker_client)
        self.cleaner = ImageCleaner(self.docker_client, self.image_name) if image_name else None
        self.summarizer = ImageSummarizer(self.docker_client, self.image_name) if image_name else None
        
    def get_images_summary(self) -> ImagesSummary:
        """
        获取镜像摘要信息

        Returns:
            ImagesSummary: 包含镜像总数、总大小、仓库分组等信息
                - total_count: 所有镜像的数量
                - total_size: 所有镜像的总大小（MB）
                - actual_disk_usage: 实际磁盘使用量（MB）
                - repos: 按仓库分组的镜像数量
                - project_images: 当前项目的镜像列表

        Raises:
            ImageBuildError: 获取镜像信息失败时抛出
        """
        if not self.summarizer:
            raise ValueError("需要提供image_name才能获取镜像摘要")
        return self.summarizer.get_summary()
        
    def build_image(
        self, dockerfile: str = "Dockerfile", build_args: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        构建Docker镜像

        Args:
            dockerfile: Dockerfile路径，相对于项目目录
            build_args: 构建参数

        Returns:
            bool: 是否构建成功
        """
        if not self.builder:
            raise ValueError("需要提供image_name才能构建镜像")
        return self.builder.build(dockerfile, build_args)
        
    def push_image(
        self,
        registry: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        prefix: Optional[str] = None,
        use_timestamp_tag: bool = False,
        use_existing_tags: bool = False
    ) -> bool:
        """
        推送镜像到远程仓库

        Args:
            registry: 远程仓库地址
            username: 仓库用户名
            password: 仓库密码
            prefix: 镜像前缀
            use_timestamp_tag: 是否使用时间戳标签推送，如果为True，会先创建时间戳标签推送，再推送latest标签
            use_existing_tags: 是否使用已有的标签 (针对save_as_image方法已创建的标签)

        Returns:
            bool: 是否推送成功

        Raises:
            ImagePushError: 推送失败时抛出
        """
        if not self.pusher:
            raise ValueError("需要提供image_name才能推送镜像")
        return self.pusher.push(registry, username, password, prefix, use_timestamp_tag, use_existing_tags)
                               
    def tag_image(self, source_tag: str, new_tag: str) -> bool:
        """
        为镜像添加新标签

        Args:
            source_tag: 源镜像标签
            new_tag: 新标签

        Returns:
            bool: 是否添加成功

        Raises:
            ImageBuildError: 添加标签失败时抛出
        """
        return self.tagger.tag(source_tag, new_tag)
        
    def cleanup_images(
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
        if not self.cleaner:
            raise ValueError("需要提供image_name才能清理镜像")
        return self.cleaner.cleanup(keep_latest, keep_days, keep_count, dry_run)
        
    def create_from_container(
        self, 
        container_name: str,
        tag: Optional[str] = None,
        repository: Optional[str] = None,
        cleanup: bool = False
    ) -> Union[str, bool]:
        """
        将容器保存为新的镜像

        Args:
            container_name: 容器名称
            tag: 镜像标签，默认使用时间戳
            repository: 镜像仓库名，默认使用容器名称
            cleanup: 是否在保存前清理容器

        Returns:
            Union[str, bool]: 成功时返回新镜像的名称，失败返回False
        """
        try:
            # 获取容器
            try:
                container = self.docker_client.containers.get(container_name)
            except Exception as e:
                logger.error(f"获取容器 {container_name} 失败: {e}")
                return False

            # 如果需要清理容器
            if cleanup:
                logger.warning("清理容器...")
                try:
                    # 清理临时文件
                    paths = ["/tmp/*", "/var/cache/*"]
                    for path in paths:
                        try:
                            container.exec_run(f"rm -rf {path}")
                        except Exception as e:
                            logger.error(f"清理路径 {path} 失败: {e}")
                    logger.success("容器缓存清理完成")
                except Exception as e:
                    logger.warning(f"清理容器失败: {e}，继续保存")

            # 设置仓库和标签
            if not repository:
                repository = container_name
                
            if not tag:
                tag = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            versioned_image_name = f"{repository}:{tag}"
            logger.warning(f"将容器保存为镜像 {versioned_image_name}...")

            # 提交容器为新镜像，添加进度提示
            logger.warning("正在提交容器状态...")
            import time
            start_time = time.time()

            # 使用低级API提交容器
            response = self.docker_client.api.commit(
                container=container_name, repository=repository, tag=tag
            )

            # 获取新创建的镜像ID
            image_id = response.get("Id", "").split(":")[-1][:12]

            # 计算耗时
            elapsed_time = time.time() - start_time
            logger.warning(f"容器状态提交完成，耗时 {elapsed_time:.2f} 秒，镜像ID: {image_id}")

            # 同时设置latest标签
            latest_image_name = f"{repository}:latest"
            try:
                logger.warning("正在设置latest标签...")
                image = self.docker_client.images.get(versioned_image_name)
                image.tag(repository=repository, tag="latest")
                logger.success(f"已为镜像 {versioned_image_name} 添加标签 {latest_image_name}")
            except Exception as e:
                logger.error(f"设置latest标签失败: {e}")

            logger.success(f"容器已保存为镜像 {versioned_image_name}")
            
            # 更新当前镜像名称以支持后续操作
            self.image_name = versioned_image_name
            
            # 重新初始化组件
            self.builder = ImageBuilder(self.docker_client, self.project_dir, self.image_name)
            self.pusher = ImagePusher(self.docker_client, self.image_name)
            self.cleaner = ImageCleaner(self.docker_client, self.image_name)
            self.summarizer = ImageSummarizer(self.docker_client, self.image_name)
            
            return versioned_image_name

        except Exception as e:
            logger.error(f"保存容器为镜像失败: {e}")
            return False
