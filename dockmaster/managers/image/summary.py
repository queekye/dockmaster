"""镜像摘要信息相关功能"""

import re
import subprocess
from datetime import datetime
from typing import Dict, List, Optional, Union

from loguru import logger

from .base import ImagesSummary, ProjectImage
from .utils import parse_image_name, parse_size_string


class ImageSummarizer:
    """镜像摘要信息管理器类"""

    def __init__(self, docker_client, image_name: str):
        """
        初始化镜像摘要信息管理器

        Args:
            docker_client: Docker客户端实例
            image_name: 镜像名称
        """
        self.docker_client = docker_client
        self.image_name = image_name

    def get_summary(self) -> ImagesSummary:
        """
        获取镜像摘要信息

        Returns:
            ImagesSummary: 包含镜像总数、总大小、仓库分组等信息
        """
        try:
            # 获取所有镜像
            all_images = self.docker_client.images.list()

            # 初始化摘要信息
            summary = {
                "total_count": len(all_images),
                "total_size": 0,  # MB
                "actual_disk_usage": 0,  # MB
                "repos": {},
                "project_images": [],
            }

            # 获取Docker系统信息，包含实际磁盘使用情况
            summary["actual_disk_usage"] = self._get_docker_disk_usage()

            # 处理镜像信息
            self._process_images_info(all_images, summary)

            return summary

        except Exception as e:
            logger.error(f"获取镜像摘要信息失败: {e}")
            return {
                "total_count": 0,
                "total_size": 0,
                "actual_disk_usage": 0,
                "repos": {},
                "project_images": [],
            }

    def _get_docker_disk_usage(self) -> float:
        """
        获取Docker磁盘使用情况

        Returns:
            float: Docker镜像实际占用的磁盘空间（MB）
        """
        try:
            # 使用docker system df命令获取实际磁盘使用情况
            result = subprocess.run(
                ["docker", "system", "df"], capture_output=True, text=True, check=True
            )

            # 解析输出，查找镜像行
            lines = result.stdout.strip().split("\n")
            for line in lines:
                if line.startswith("Images"):
                    # 格式通常是: Images     数量     大小     RECLAIMABLE
                    parts = re.split(r"\s+", line.strip())
                    if len(parts) >= 4:
                        # 解析大小字符串（例如：5.629GB）
                        size_str = parts[2]
                        size_mb = parse_size_string(size_str)
                        return round(size_mb, 2)

            # 如果上面的方法失败，尝试使用docker info命令
            result = subprocess.run(
                ["docker", "info", "--format", "{{.Driver}}"],
                capture_output=True,
                text=True,
                check=True,
            )

            # 获取存储驱动类型
            storage_driver = result.stdout.strip()

            # 如果是overlay2，可以通过du命令获取实际使用量
            if storage_driver == "overlay2":
                result = subprocess.run(
                    ["sudo", "du", "-sm", "/var/lib/docker/overlay2"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    size_mb = float(result.stdout.split()[0])
                    return round(size_mb, 2)

        except Exception as e:
            logger.warning(f"获取Docker系统信息失败，无法计算实际磁盘使用量: {e}")
            
        return 0.0

    def _process_images_info(self, all_images: List, summary: Dict) -> None:
        """
        处理镜像信息

        Args:
            all_images: 所有镜像列表
            summary: 摘要信息字典
        """
        # 获取当前项目的基础镜像名称
        base_image_name, _ = parse_image_name(self.image_name)
        
        # 按仓库分组
        for image in all_images:
            # 计算大小（转换为MB）
            # Docker镜像大小是通过image.attrs['Size']获取的，单位为字节，这里转换为MB
            size_mb = round(image.attrs["Size"] / (1024 * 1024), 2)
            summary["total_size"] += size_mb

            # 如果没有标签，跳过
            if not image.tags:
                continue

            for tag in image.tags:
                if ":" in tag:
                    repo, tag_name = tag.split(":", 1)

                    # 更新仓库计数
                    if repo not in summary["repos"]:
                        summary["repos"][repo] = 0
                    summary["repos"][repo] += 1

                    # 如果是当前项目的镜像，添加到项目镜像列表
                    if repo.startswith(base_image_name):
                        self._add_project_image(image, tag, tag_name, size_mb, summary)

        # 对项目镜像按创建时间排序
        summary["project_images"].sort(key=lambda x: x["created"], reverse=True)

        # 四舍五入总大小
        summary["total_size"] = round(summary["total_size"], 2)

    def _add_project_image(
        self, image, tag: str, tag_name: str, size_mb: float, summary: Dict
    ) -> None:
        """
        添加项目镜像到摘要

        Args:
            image: Docker镜像对象
            tag: 完整标签
            tag_name: 标签名称
            size_mb: 镜像大小（MB）
            summary: 摘要信息字典
        """
        try:
            created_time = datetime.strptime(
                image.attrs["Created"].split(".")[0], "%Y-%m-%dT%H:%M:%S"
            )

            project_image: ProjectImage = {
                "id": image.id,
                "tag": tag_name,
                "full_tag": tag,
                "created": image.attrs["Created"],
                "created_time": created_time,
                "size_mb": size_mb,
                "created_ago": (datetime.now() - created_time).days,
            }
            
            summary["project_images"].append(project_image)
        except Exception as e:
            logger.error(f"处理项目镜像信息失败: {e}") 