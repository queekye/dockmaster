"""镜像管理器类"""

import os
import json
import subprocess
import docker
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path
from datetime import datetime, timedelta

from .base_manager import BaseManager
from loguru import logger
from ..utils import run_command, confirm_action, get_timestamp, create_temp_file


class ImageBuildError(Exception):
    """镜像构建错误"""
    pass

class ImagePushError(Exception):
    """镜像推送错误"""
    pass

class ImageManager(BaseManager):
    """镜像管理器类，用于构建和推送镜像"""
    
    def __init__(self, project_dir: str, image_name: str):
        """
        初始化镜像管理器
        
        Args:
            project_dir: 项目目录路径
            image_name: 镜像名称
        """
        super().__init__()
        self.project_dir = Path(project_dir)
        self.image_name = image_name
        
    def get_images_summary(self) -> Dict[str, Any]:
        """
        获取镜像摘要信息
        
        Returns:
            Dict[str, Any]: 包含镜像总数、总大小、仓库分组等信息
                - total_count: 所有镜像的数量
                - total_size: 所有镜像的总大小（MB）
                - actual_disk_usage: 实际磁盘使用量（MB）
                - repos: 按仓库分组的镜像数量
                - project_images: 当前项目的镜像列表，每个镜像包含:
                    - id: 镜像ID
                    - tag: 镜像标签
                    - full_tag: 完整的镜像名称（包含仓库和标签）
                    - created: 创建时间
                    - created_time: 解析后的创建时间对象
                    - size_mb: 镜像大小（MB）
                    - created_ago: 创建至今的天数
        """
        try:
            # 获取所有镜像
            all_images = self.docker_client.images.list()
            
            # 初始化摘要信息
            summary = {
                'total_count': len(all_images),
                'total_size': 0,  # MB
                'actual_disk_usage': 0,  # MB
                'repos': {},
                'project_images': []
            }
            
            # 获取Docker系统信息，包含实际磁盘使用情况
            try:
                # 使用docker system df命令获取实际磁盘使用情况
                import json
                import subprocess
                import re
                
                # 执行docker system df命令获取镜像使用情况
                result = subprocess.run(
                    ["docker", "system", "df"], 
                    capture_output=True, 
                    text=True, 
                    check=True
                )
                
                # 解析输出，查找镜像行
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if line.startswith('Images'):
                        # 格式通常是: Images     数量     大小     RECLAIMABLE
                        parts = re.split(r'\s+', line.strip())
                        if len(parts) >= 4:
                            # 解析大小字符串（例如：5.629GB）
                            size_str = parts[2]
                            size_value = float(re.match(r'([\d.]+)', size_str).group(1))
                            
                            # 转换为MB
                            if 'GB' in size_str:
                                size_mb = size_value * 1024
                            elif 'MB' in size_str:
                                size_mb = size_value
                            elif 'KB' in size_str:
                                size_mb = size_value / 1024
                            elif 'B' in size_str:
                                size_mb = size_value / (1024 * 1024)
                            else:
                                size_mb = size_value
                                
                            summary['actual_disk_usage'] = round(size_mb, 2)
                            break
                
                # 如果上面的方法失败，尝试使用docker info命令
                if summary['actual_disk_usage'] == 0:
                    result = subprocess.run(
                        ["docker", "info", "--format", "{{.Driver}}"], 
                        capture_output=True, 
                        text=True, 
                        check=True
                    )
                    
                    # 获取存储驱动类型
                    storage_driver = result.stdout.strip()
                    
                    # 如果是overlay2，可以通过du命令获取实际使用量
                    if storage_driver == 'overlay2':
                        result = subprocess.run(
                            ["sudo", "du", "-sm", "/var/lib/docker/overlay2"], 
                            capture_output=True, 
                            text=True
                        )
                        if result.returncode == 0:
                            size_mb = float(result.stdout.split()[0])
                            summary['actual_disk_usage'] = round(size_mb, 2)
            except Exception as e:
                logger.warning(f"获取Docker系统信息失败，无法计算实际磁盘使用量: {e}")
                # 如果获取失败，使用传统方式计算（可能不准确）
                summary['actual_disk_usage'] = None
            
            # 按仓库分组
            for image in all_images:
                # 计算大小（转换为MB）
                # Docker镜像大小是通过image.attrs['Size']获取的，单位为字节，这里转换为MB
                size_mb = round(image.attrs['Size'] / (1024 * 1024), 2)
                summary['total_size'] += size_mb
                
                # 如果没有标签，跳过
                if not image.tags:
                    continue
                    
                for tag in image.tags:
                    if ':' in tag:
                        repo, tag_name = tag.split(':', 1)
                        
                        # 更新仓库计数
                        if repo not in summary['repos']:
                            summary['repos'][repo] = 0
                        summary['repos'][repo] += 1
                        
                        # 如果是当前项目的镜像，添加到项目镜像列表
                        if repo.startswith(self.image_name.split(':')[0]):
                            created_time = datetime.strptime(
                                image.attrs['Created'].split('.')[0], 
                                '%Y-%m-%dT%H:%M:%S'
                            )
                            
                            summary['project_images'].append({
                                'id': image.id,
                                'tag': tag_name,
                                'full_tag': tag,
                                'created': image.attrs['Created'],
                                'created_time': created_time,
                                'size_mb': size_mb,
                                'created_ago': (datetime.now() - created_time).days
                            })
            
            # 对项目镜像按创建时间排序
            summary['project_images'].sort(key=lambda x: x['created'], reverse=True)
            
            # 四舍五入总大小
            summary['total_size'] = round(summary['total_size'], 2)
            
            return summary
            
        except Exception as e:
            logger.error(f"获取镜像摘要信息失败: {e}")
            return {
                'total_count': 0,
                'total_size': 0,
                'actual_disk_usage': 0,
                'repos': {},
                'project_images': []
            }
        
    def build_image(self, dockerfile: str = 'Dockerfile', build_args: Dict[str, str] = None) -> bool:
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
                build_result = self.docker_client.api.build(
                    path=str(self.project_dir),
                    dockerfile=str(dockerfile_path),
                    tag=versioned_image_name,
                    buildargs=build_args or {},
                    decode=True,
                    rm=True
                )
                
                # 处理构建输出
                for line in build_result:
                    if 'stream' in line:
                        log_line = line['stream'].strip()
                        if log_line:
                            logger.warning(log_line)
                    elif 'error' in line:
                        raise ImageBuildError(line['error'])
                    elif 'status' in line:
                        logger.warning(line['status'])
                
                # 同时设置latest标签
                latest_image_name = f"{self.image_name}:latest"
                self.tag_image(versioned_image_name, latest_image_name)
                
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
    
    def push_image(self, registry: str = None, username: str = None, password: str = None, prefix: str = None) -> bool:
        """
        推送镜像到远程仓库
        
        Args:
            registry: 远程仓库地址
            username: 用户名
            password: 密码，如果为None，会尝试从环境变量获取
            prefix: 镜像前缀，优先于username作为命名空间
            
        Returns:
            bool: 是否推送成功
        """
        try:
            original_image_name = self.image_name
            
            # 确定命名空间（优先使用prefix，其次使用username）
            namespace = prefix or username
            
            # 检查镜像名称是否已包含命名空间
            if namespace and '/' not in self.image_name:
                # 自动添加命名空间前缀
                self.image_name = f"{namespace}/{self.image_name}"
                logger.info(f"自动添加命名空间: {self.image_name}")
                
                # 为原始镜像添加新标签
                try:
                    image = self.docker_client.images.get(original_image_name)
                    image.tag(self.image_name)
                    logger.success(f"已为镜像 {original_image_name} 添加标签 {self.image_name}")
                except Exception as e:
                    logger.error(f"添加标签失败: {e}")
                    return False
            
            if registry:
                # 重新标记镜像
                new_tag = f"{registry}/{self.image_name}"
                image = self.docker_client.images.get(self.image_name)
                image.tag(new_tag)
                target_image = new_tag
            else:
                target_image = self.image_name
            
            # 如果没有提供密码，尝试从环境变量获取
            if username and not password:
                env_var_name = f"DOCKER_PASSWORD_{username.upper()}"
                password = os.environ.get(env_var_name) or os.environ.get("DOCKER_PASSWORD")
                if password:
                    logger.info(f"已从环境变量获取密码")
                else:
                    logger.warning(f"未找到密码，请设置环境变量 {env_var_name} 或 DOCKER_PASSWORD")
                    logger.warning(f"或者使用 'docker login -u {username}' 命令手动登录")
            
            # 登录仓库
            if username and password:
                try:
                    logger.info(f"正在登录仓库 {registry or 'docker.io'} 用户名: {username}")
                    self.docker_client.login(
                        registry=registry,
                        username=username,
                        password=password
                    )
                    logger.success(f"登录仓库成功")
                except docker.errors.APIError as e:
                    error_msg = f"登录远程仓库失败: {e}"
                    logger.error(error_msg)
                    if "unauthorized" in str(e).lower():
                        logger.error("认证失败，请检查用户名和密码是否正确")
                        logger.error(f"您可以设置环境变量 {f'DOCKER_PASSWORD_{username.upper()}' if username else 'DOCKER_PASSWORD'} 提供密码")
                        logger.error("或者尝试先使用 'docker login -u " + username + "' 命令手动登录")
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
            
            logger.warning(f"开始推送镜像 {target_image}...")
            
            # 推送镜像
            push_output = []
            for line in self.docker_client.images.push(
                target_image,
                stream=True,
                decode=True
            ):
                if 'error' in line:
                    error_msg = line['error']
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
                            logger.error(f"或者尝试先使用 'docker login -u {username}' 命令手动登录")
                        else:
                            logger.error("或者尝试先使用 'docker login' 命令手动登录")
                    elif "not found" in error_msg.lower():
                        logger.error("镜像或仓库未找到，请检查名称是否正确")
                    
                    # 恢复原始镜像名称
                    self.image_name = original_image_name
                    raise ImagePushError(error_msg)
                elif 'status' in line:
                    logger.warning(line['status'])
                    push_output.append(line['status'])
            
            # 检查推送结果
            if any("digest: sha256" in line for line in push_output):
                logger.success(f"镜像 {target_image} 推送成功")
                # 恢复原始镜像名称
                self.image_name = original_image_name
                return True
            else:
                logger.warning("推送可能未完成，请检查输出信息")
                # 恢复原始镜像名称
                self.image_name = original_image_name
                return False
            
        except ImagePushError as e:
            logger.error(f"推送镜像失败: {e}")
            return False
        except docker.errors.ImageNotFound:
            logger.error(f"镜像 {self.image_name} 不存在，请先构建镜像")
            return False
        except Exception as e:
            logger.error(f"推送镜像失败: {e}")
            return False
    
    def tag_image(self, source_tag: str, new_tag: str) -> bool:
        """
        为镜像添加新标签
        
        Args:
            source_tag: 源镜像标签
            new_tag: 新标签名称
            
        Returns:
            bool: 是否添加成功
        """
        try:
            image = self.docker_client.images.get(source_tag)
            image.tag(new_tag)
            logger.success(f"已为镜像 {source_tag} 添加标签 {new_tag}")
            return True
        except Exception as e:
            logger.error(f"添加标签失败: {e}")
            return False
    
    def cleanup_images(self, keep_latest: bool = True, keep_days: int = None, keep_count: int = None, dry_run: bool = False) -> Tuple[List[str], List[str]]:
        """
        清理历史镜像
        
        Args:
            keep_latest: 是否保留latest标签的镜像
            keep_days: 保留最近几天的镜像，None表示不按时间清理
            keep_count: 为每个仓库保留的最新镜像数量，None表示不按数量清理
            dry_run: 是否只是模拟运行，不实际删除
            
        Returns:
            Tuple[List[str], List[str]]: 已删除的镜像列表和保留的镜像列表
        """
        try:
            import re
            from datetime import datetime, timedelta
            
            # 获取所有镜像
            all_images = self.docker_client.images.list()
            
            # 按仓库分组
            repo_images = {}
            for image in all_images:
                for tag in image.tags:
                    if ':' in tag:
                        repo, tag_name = tag.split(':', 1)
                        if repo not in repo_images:
                            repo_images[repo] = []
                        repo_images[repo].append({
                            'id': image.id,
                            'tag': tag_name,
                            'full_tag': tag,
                            'created': image.attrs['Created']
                        })
            
            to_delete = []
            to_keep = []
            
            # 处理每个仓库的镜像
            for repo, images in repo_images.items():
                # 如果不是当前项目的镜像，跳过
                if not repo.startswith(self.image_name.split(':')[0]):
                    continue
                
                # 按创建时间排序
                images.sort(key=lambda x: x['created'], reverse=True)
                
                # 标记要保留的latest镜像
                latest_image_id = None
                if keep_latest:
                    for img in images:
                        if img['tag'] == 'latest':
                            latest_image_id = img['id']
                            to_keep.append(img['full_tag'])
                            break
                
                # 按时间筛选
                if keep_days is not None:
                    cutoff_date = datetime.now() - timedelta(days=keep_days)
                    cutoff_date_str = cutoff_date.strftime('%Y-%m-%dT%H:%M:%S')
                    
                    for img in images:
                        # 如果是latest且需要保留，则跳过
                        if keep_latest and img['id'] == latest_image_id:
                            continue
                            
                        # 检查是否是时间戳格式的标签
                        if re.match(r'^\d{8}_\d{6}$', img['tag']):
                            if img['created'] < cutoff_date_str:
                                to_delete.append(img['full_tag'])
                            else:
                                to_keep.append(img['full_tag'])
                
                # 按数量筛选
                elif keep_count is not None:
                    # 过滤出时间戳格式的标签
                    timestamp_images = [img for img in images if re.match(r'^\d{8}_\d{6}$', img['tag'])]
                    
                    # 保留指定数量的最新镜像
                    for i, img in enumerate(timestamp_images):
                        # 如果是latest且需要保留，则跳过
                        if keep_latest and img['id'] == latest_image_id:
                            continue
                            
                        if i < keep_count:
                            to_keep.append(img['full_tag'])
                        else:
                            to_delete.append(img['full_tag'])
            
            # 如果是dry run，只返回结果不删除
            if dry_run:
                return to_delete, to_keep
            
            # 执行删除
            deleted = []
            for tag in to_delete:
                try:
                    self.docker_client.images.remove(tag)
                    deleted.append(tag)
                    logger.info(f"已删除镜像: {tag}")
                except Exception as e:
                    logger.error(f"删除镜像 {tag} 失败: {e}")
            
            return deleted, to_keep
            
        except Exception as e:
            logger.error(f"清理镜像失败: {e}")
            return [], [] 