"""容器监控工具，负责容器日志和状态监控"""

import time
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

import docker
from docker.errors import APIError, NotFound
from docker.models.containers import Container
from loguru import logger

from .base_manager import BaseManager


class ContainerMonitor(BaseManager):
    """容器监控类，用于监控容器日志和状态"""
    
    project_dir: Path
    container_name: str
    
    def __init__(self, project_dir: str, container_name: str) -> None:
        """
        初始化容器监控器
        
        Args:
            project_dir: 项目目录路径
            container_name: 容器名称
        """
        super().__init__()
        self.project_dir = Path(project_dir)
        self.container_name = container_name
    
    def _get_container(self) -> Optional[Container]:
        """获取容器对象，如果不存在返回None"""
        try:
            return self.docker_client.containers.get(self.container_name)
        except NotFound:
            logger.warning(f"容器 {self.container_name} 不存在")
            return None
        except Exception as e:
            logger.error(f"获取容器失败: {e}")
            return None
    
    def show_logs(self, follow: bool = False, tail: int = 100) -> bool:
        """
        显示容器日志
        
        Args:
            follow: 是否持续显示日志
            tail: 返回的日志行数
            
        Returns:
            bool: 是否成功显示日志
        """
        try:
            container = self._get_container()
            if not container:
                return False

            if container.status != "running":
                logger.warning(f"容器 {self.container_name} 未运行")
                return False

            logger.debug(f"显示容器 {self.container_name} 的日志:")

            if follow:
                # 持续显示日志
                for line in container.logs(stream=True, follow=True):
                    print(line.decode("utf-8").strip())
            else:
                # 显示最近的日志
                logs = container.logs(tail=tail).decode("utf-8")
                print(logs)

            return True

        except Exception as e:
            logger.error(f"显示容器日志失败: {e}")
            return False
    
    def get_container_stats(self) -> Dict[str, Any]:
        """
        获取容器资源使用情况
        
        Returns:
            Dict[str, Any]: 包含CPU、内存等使用情况
        """
        try:
            container = self._get_container()
            if not container:
                return {"error": "容器不存在"}
                
            if container.status != "running":
                return {"status": container.status, "error": "容器未运行"}
                
            stats = container.stats(stream=False)
            
            # 处理CPU使用率
            cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"]["total_usage"]
            system_delta = stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]
            cpu_percent = 0.0
            if system_delta > 0 and cpu_delta > 0:
                cpu_percent = (cpu_delta / system_delta) * len(stats["cpu_stats"]["cpu_usage"]["percpu_usage"]) * 100.0
                
            # 处理内存使用率
            mem_usage = stats["memory_stats"].get("usage", 0)
            mem_limit = stats["memory_stats"].get("limit", 1)
            mem_percent = (mem_usage / mem_limit) * 100.0
            
            return {
                "status": container.status,
                "id": container.id[:12],
                "cpu_percent": round(cpu_percent, 2),
                "mem_usage": mem_usage,
                "mem_limit": mem_limit,
                "mem_percent": round(mem_percent, 2),
                "network_rx": stats.get("networks", {}).get("eth0", {}).get("rx_bytes", 0),
                "network_tx": stats.get("networks", {}).get("eth0", {}).get("tx_bytes", 0)
            }
            
        except Exception as e:
            logger.error(f"获取容器资源使用情况失败: {e}")
            return {"error": str(e)}
    
    def check_container_health(self) -> Dict[str, Any]:
        """
        检查容器健康状态
        
        Returns:
            Dict[str, Any]: 容器健康信息
        """
        try:
            container = self._get_container()
            if not container:
                return {"status": "not_found", "healthy": False}
                
            inspect = container.attrs
            
            # 检查容器状态
            status = container.status
            
            # 检查健康检查结果（如果有配置）
            health_status = None
            if "Health" in inspect["State"]:
                health_status = inspect["State"]["Health"]["Status"]
                
            return {
                "status": status,
                "id": container.id[:12],
                "running": status == "running",
                "healthy": health_status == "healthy" if health_status else status == "running",
                "health_status": health_status,
                "started_at": inspect["State"]["StartedAt"],
                "restart_count": inspect["RestartCount"] if "RestartCount" in inspect else 0
            }
            
        except Exception as e:
            logger.error(f"检查容器健康状态失败: {e}")
            return {"status": "error", "healthy": False, "error": str(e)} 