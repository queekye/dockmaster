"""镜像推送相关功能"""

import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import docker
from loguru import logger

from .base import ImagePushError
from .tag import ImageTagger
from .utils import parse_image_name


class ImagePusher:
    """镜像推送器类"""

    def __init__(self, docker_client, image_name: str):
        """
        初始化镜像推送器

        Args:
            docker_client: Docker客户端实例
            image_name: 镜像名称
        """
        self.docker_client = docker_client
        self.image_name = image_name
        self.tagger = ImageTagger(docker_client)

    def push(
        self,
        registry: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        prefix: Optional[str] = None,
        use_timestamp_tag: bool = False,
        use_existing_tags: bool = False,
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
        try:
            original_image_name = self.image_name

            # 准备要推送的镜像标签
            images_to_push = self._prepare_image_tags(
                registry, username, prefix, use_timestamp_tag, use_existing_tags
            )

            # 获取密码
            if username and not password:
                password = self._get_password_from_env(username)

            # 登录Docker仓库
            self._do_login(registry, username, password)

            # 推送镜像
            push_success = self._push_images(images_to_push, username)

            # 恢复原始镜像名称
            self.image_name = original_image_name
            return push_success

        except ImagePushError as e:
            logger.error(f"推送镜像失败: {e}")
            # 恢复原始镜像名称
            self.image_name = original_image_name
            return False
        except docker.errors.ImageNotFound:
            logger.error(f"镜像 {self.image_name} 不存在，请先构建镜像")
            # 恢复原始镜像名称
            self.image_name = original_image_name
            return False
        except Exception as e:
            logger.error(f"推送镜像失败: {e}")
            # 恢复原始镜像名称
            self.image_name = original_image_name
            return False

    def _prepare_image_tags(
        self,
        registry: Optional[str],
        username: Optional[str],
        prefix: Optional[str],
        use_timestamp_tag: bool,
        use_existing_tags: bool,
    ) -> List[str]:
        """
        准备要推送的镜像标签

        Args:
            registry: 远程仓库地址
            username: 仓库用户名
            prefix: 镜像前缀
            use_timestamp_tag: 是否使用时间戳标签
            use_existing_tags: 是否使用已有标签

        Returns:
            List[str]: 要推送的镜像标签列表
        """
        # 解析原始镜像名称
        repository, tag = parse_image_name(self.image_name)
        
        # 确定命名空间（优先使用prefix，其次使用username）
        namespace = prefix or username
        
        images_to_push = []
        timestamp_image_name = None
        
        # 如果使用已有的标签，需要推送两个标签 (时间戳和latest)
        if use_existing_tags:
            # 这里假设当前的image_name已经是带时间戳的标签
            # 获取repository部分
            timestamp_image_name = self.image_name
            # 构造latest镜像名称
            latest_image_name = f"{repository}:latest"
        # 如果使用时间戳标签但不使用已有标签，需要创建新标签
        elif use_timestamp_tag:
            # 创建时间戳标签
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            timestamp_image_name = f"{repository}:{timestamp}"
            
            # 为原始镜像添加时间戳标签
            try:
                image = self.docker_client.images.get(self.image_name)
                image.tag(repository=repository, tag=timestamp)
                logger.success(f"已为镜像 {self.image_name} 添加时间戳标签 {timestamp_image_name}")
                
                # 设置当前镜像名称为时间戳标签镜像
                self.image_name = timestamp_image_name
            except Exception as e:
                logger.error(f"添加时间戳标签失败: {e}")
                return []
        
        # 处理时间戳标签和latest标签
        if timestamp_image_name:
            # 添加命名空间和注册表前缀
            timestamp_target = timestamp_image_name
            if namespace:
                timestamp_target = self.tagger.add_namespace_prefix(timestamp_target, namespace)
            if registry:
                timestamp_target = self.tagger.add_registry_prefix(timestamp_target, registry)
            
            images_to_push.append(timestamp_target)
            
            # 如果使用已有标签或时间戳标签，还需要推送latest标签
            latest_image_name = f"{repository}:latest"
            latest_target = latest_image_name
            
            # 添加命名空间和注册表前缀
            if namespace:
                latest_target = self.tagger.add_namespace_prefix(latest_target, namespace)
            if registry:
                latest_target = self.tagger.add_registry_prefix(latest_target, registry)
            
            images_to_push.append(latest_target)
        else:
            # 如果不使用时间戳标签和已有标签，直接处理原始镜像名称
            target_image = self.image_name
            
            # 添加命名空间和注册表前缀
            if namespace:
                target_image = self.tagger.add_namespace_prefix(target_image, namespace)
            if registry:
                target_image = self.tagger.add_registry_prefix(target_image, registry)
            
            images_to_push.append(target_image)
        
        return images_to_push

    def _get_password_from_env(self, username: str) -> Optional[str]:
        """
        从环境变量获取密码

        Args:
            username: 用户名

        Returns:
            Optional[str]: 从环境变量获取的密码，如果未找到则返回None
        """
        env_var_name = f"DOCKER_PASSWORD_{username.upper()}"
        password = os.environ.get(env_var_name) or os.environ.get("DOCKER_PASSWORD")
        if password:
            logger.info(f"已从环境变量获取密码")
        else:
            logger.warning(f"未找到密码，请设置环境变量 {env_var_name} 或 DOCKER_PASSWORD")
            logger.warning(f"或者使用 'docker login -u {username}' 命令手动登录")
        return password

    def _do_login(
        self, registry: Optional[str], username: Optional[str], password: Optional[str]
    ) -> bool:
        """
        登录Docker仓库

        Args:
            registry: 远程仓库地址
            username: 仓库用户名
            password: 仓库密码

        Returns:
            bool: 是否登录成功

        Raises:
            ImagePushError: 登录失败时抛出
        """
        # 登录仓库
        if username and password:
            try:
                logger.info(f"正在登录仓库 {registry or 'docker.io'} 用户名: {username}")
                self.docker_client.login(registry=registry, username=username, password=password)
                logger.success(f"登录仓库成功")
                return True
            except docker.errors.APIError as e:
                error_msg = f"登录远程仓库失败: {e}"
                logger.error(error_msg)
                if "unauthorized" in str(e).lower():
                    logger.error("认证失败，请检查用户名和密码是否正确")
                    logger.error(
                        f"您可以设置环境变量 {f'DOCKER_PASSWORD_{username.upper()}' if username else 'DOCKER_PASSWORD'} 提供密码"
                    )
                    logger.error(
                        "或者尝试先使用 'docker login -u " + username + "' 命令手动登录"
                    )
                elif "connection" in str(e).lower():
                    logger.error("连接失败，请检查网络连接和仓库地址是否正确")
                raise ImagePushError(error_msg)
        elif registry:
            logger.warning(f"未提供用户名和密码，将尝试匿名推送到 {registry}")
            logger.warning(f"如果失败，请尝试先使用 'docker login {registry}' 命令手动登录")
        else:
            logger.warning("未提供仓库信息，将尝试推送到默认仓库")
            if username:
                logger.warning(f"如果失败，请尝试先使用 'docker login -u {username}' 命令手动登录")
            else:
                logger.warning("如果失败，请尝试先使用 'docker login' 命令手动登录")
        return False

    def _push_images(self, images_to_push: List[str], username: Optional[str]) -> bool:
        """
        推送镜像到仓库

        Args:
            images_to_push: 要推送的镜像列表
            username: 用户名，用于错误提示

        Returns:
            bool: 是否全部推送成功
        """
        # 按顺序推送所有镜像
        push_success = True
        for img in images_to_push:
            if not self._do_push_single_image(img, username):
                push_success = False
                logger.error(f"推送镜像 {img} 失败")
        
        return push_success

    def _do_push_single_image(self, img_name: str, username: Optional[str]) -> bool:
        """
        推送单个镜像

        Args:
            img_name: 镜像名称
            username: 用户名，用于错误提示

        Returns:
            bool: 是否推送成功
        """
        logger.warning(f"开始推送镜像 {img_name}...")
        push_output = []
        try:
            for line in self.docker_client.images.push(img_name, stream=True, decode=True):
                if "error" in line:
                    error_msg = line["error"]
                    logger.error(f"推送错误: {error_msg}")

                    # 提供更友好的错误信息
                    if "denied" in error_msg.lower() and "access" in error_msg.lower():
                        logger.error("访问被拒绝，可能是因为：")
                        logger.error("1. 用户名或密码错误")
                        logger.error("2. 用户没有推送权限")
                        logger.error("3. 仓库不存在或需要先创建")
                        logger.error("4. 镜像名称格式不正确，应为 '用户名/镜像名'")
                        logger.error("请使用 'dm config' 命令配置正确的仓库信息")
                        if username:
                            logger.error(
                                f"或者尝试先使用 'docker login -u {username}' 命令手动登录"
                            )
                        else:
                            logger.error("或者尝试先使用 'docker login' 命令手动登录")
                    elif "not found" in error_msg.lower():
                        logger.error("镜像或仓库未找到，请检查名称是否正确")

                    raise ImagePushError(error_msg)
                elif "status" in line:
                    logger.warning(line["status"])
                    push_output.append(line["status"])

            # 检查推送结果
            if any("digest: sha256" in line for line in push_output):
                logger.success(f"镜像 {img_name} 推送成功")
                return True
            else:
                logger.warning(f"镜像 {img_name} 推送可能未完成，请检查输出信息")
                return False
        except docker.errors.ImageNotFound:
            logger.error(f"镜像 {img_name} 不存在，跳过推送")
            return False 