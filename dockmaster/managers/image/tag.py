"""镜像标签管理相关功能"""

from loguru import logger

from .base import ImageBuildError


class ImageTagger:
    """镜像标签管理器类"""

    def __init__(self, docker_client):
        """
        初始化镜像标签管理器

        Args:
            docker_client: Docker客户端实例
        """
        self.docker_client = docker_client

    def tag(self, source_tag: str, new_tag: str) -> bool:
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
        try:
            image = self.docker_client.images.get(source_tag)
            image.tag(new_tag)
            logger.success(f"已为镜像 {source_tag} 添加标签 {new_tag}")
            return True
        except Exception as e:
            logger.error(f"添加标签失败: {e}")
            return False

    def add_namespace_prefix(self, image_tag: str, namespace: str) -> str:
        """
        为镜像添加命名空间前缀

        Args:
            image_tag: 镜像标签
            namespace: 命名空间

        Returns:
            str: 添加前缀后的镜像标签
        """
        if namespace and "/" not in image_tag:
            target_tag = f"{namespace}/{image_tag}"
            try:
                image = self.docker_client.images.get(image_tag)
                image.tag(target_tag)
                logger.success(f"已为镜像 {image_tag} 添加标签 {target_tag}")
                return target_tag
            except Exception as e:
                logger.error(f"添加命名空间前缀标签失败: {e}")
                return image_tag
        return image_tag

    def add_registry_prefix(self, image_tag: str, registry: str) -> str:
        """
        为镜像添加注册表前缀

        Args:
            image_tag: 镜像标签
            registry: 注册表

        Returns:
            str: 添加前缀后的镜像标签
        """
        if registry:
            registry_target = f"{registry}/{image_tag}"
            try:
                image = self.docker_client.images.get(image_tag)
                image.tag(registry_target)
                logger.success(f"已为镜像 {image_tag} 添加标签 {registry_target}")
                return registry_target
            except Exception as e:
                logger.error(f"添加仓库前缀标签失败: {e}")
                return image_tag
        return image_tag 