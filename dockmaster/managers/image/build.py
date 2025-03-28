"""镜像构建相关功能"""

from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import docker
from loguru import logger

from .base import ImageBuildError
from .tag import ImageTagger


class ImageBuilder:
    """镜像构建器类"""

    def __init__(self, docker_client, project_dir: Path, image_name: str) -> None:
        """
        初始化镜像构建器

        Args:
            docker_client: Docker客户端实例
            project_dir: 项目目录路径
            image_name: 镜像名称
        """
        self.docker_client = docker_client
        self.project_dir = Path(project_dir) if isinstance(project_dir, str) else project_dir
        self.image_name = image_name
        self.tagger = ImageTagger(docker_client)

    def build(
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
        try:
            dockerfile_path = self.project_dir / dockerfile
            if not dockerfile_path.exists():
                raise ImageBuildError(f"Dockerfile不存在: {dockerfile_path}")

            # 生成带日期时间的标签
            timestamp_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
            versioned_image_name = f"{self.image_name}:{timestamp_tag}"

            logger.warning(f"开始构建镜像 {versioned_image_name}...")

            # 构建镜像，使用stream=True获取构建进度
            try:
                # 使用Docker API构建镜像
                build_result = self._build_with_progress(
                    dockerfile_path, versioned_image_name, build_args or {}
                )

                # 同时设置latest标签
                latest_image_name = f"{self.image_name}:latest"
                self.tagger.tag(versioned_image_name, latest_image_name)

                # 记录日志但不输出到控制台
                logger.info(f"镜像 {versioned_image_name} 构建成功，并设置为latest")
                logger.success(f"镜像 {versioned_image_name} 构建成功，并设置为latest")
                return True
            except docker.errors.BuildError as e:
                logger.error(f"构建镜像失败: {e}")
                logger.error(f"构建日志:\n{e.build_log}")
                return False

        except Exception as e:
            logger.error(f"构建镜像失败: {e}")
            return False

    def _build_with_progress(
        self, dockerfile_path: Path, image_name: str, build_args: Dict[str, str]
    ) -> bool:
        """
        构建镜像并显示进度

        Args:
            dockerfile_path: Dockerfile路径
            image_name: 镜像名称
            build_args: 构建参数

        Returns:
            bool: 是否构建成功

        Raises:
            ImageBuildError: 构建失败时抛出
        """
        build_result = self.docker_client.api.build(
            path=str(self.project_dir),
            dockerfile=str(dockerfile_path),
            tag=image_name,
            buildargs=build_args,
            decode=True,
            rm=True,
        )

        # 处理构建输出
        for line in build_result:
            if "stream" in line:
                log_line = line["stream"].strip()
                if log_line:
                    logger.warning(log_line)
            elif "error" in line:
                raise ImageBuildError(line["error"])
            elif "status" in line:
                logger.warning(line["status"])

        return True 