"""配置管理器类"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Type, Union, TypeVar, cast

from loguru import logger

from ..constants import DEFAULT_PROJECT_CONFIG, DefaultProjectConfig
from .base_manager import BaseManager


class ConfigError(Exception):
    """配置错误"""

    pass


T = TypeVar('T')
ValidationStructure = Dict[str, Union[Type[Any], 'ValidationStructure']]

def generate_validation_structure(config_template: Dict[str, Any]) -> ValidationStructure:
    """
    从配置模板生成验证结构

    Args:
        config_template: 配置模板

    Returns:
        ValidationStructure: 验证结构
    """
    validation_structure: ValidationStructure = {}

    for key, value in config_template.items():
        if isinstance(value, dict):
            validation_structure[key] = generate_validation_structure(value)
        elif isinstance(value, list):
            validation_structure[key] = list
        elif value is None:
            validation_structure[key] = str
        else:
            validation_structure[key] = type(value)

    return validation_structure


class ConfigManager(BaseManager):
    """配置管理器类，用于管理项目配置"""

    project_name: str
    project_dir: str
    config: DefaultProjectConfig
    REQUIRED_CONFIG_FIELDS: ValidationStructure

    def __init__(self, project_name: str, project_dir: Optional[str] = None, config: Optional[DefaultProjectConfig] = None) -> None:
        """
        初始化配置管理器

        Args:
            project_name: 项目名称
            project_dir: 项目目录路径，默认为None
            config: 项目配置，默认为None
        """
        super().__init__()
        self.project_name = project_name
        self.project_dir = project_dir or os.getcwd()
        self.config = config or cast(DefaultProjectConfig, {})

        # 初始化验证结构
        self.REQUIRED_CONFIG_FIELDS = generate_validation_structure(DEFAULT_PROJECT_CONFIG)

    def create_default_config(self) -> DefaultProjectConfig:
        """
        创建默认配置

        Returns:
            DefaultProjectConfig: 默认配置
        """
        # 使用constants中的DEFAULT_PROJECT_CONFIG作为基础
        config = cast(DefaultProjectConfig, DEFAULT_PROJECT_CONFIG.copy())

        # 填充项目特定的值
        config["project"]["name"] = self.project_name
        config["project"]["directory"] = self.project_dir
        config["image"]["name"] = self.project_name
        config["container"]["name"] = self.project_name

        self.config = config
        return config

    def load_config(self) -> DefaultProjectConfig:
        """
        加载配置文件

        Returns:
            DefaultProjectConfig: 加载的配置

        Raises:
            ConfigError: 配置加载失败时抛出
        """
        config_file = os.path.join(self.project_dir, "config.json")
        if not os.path.exists(config_file):
            raise ConfigError(f"项目配置文件不存在: {config_file}")

        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)

        self.config = config
        self.validate_config()
        return config

    def update_config(self, config_updates: Dict[str, Any]) -> DefaultProjectConfig:
        """
        更新配置

        Args:
            config_updates: 要更新的配置项

        Returns:
            DefaultProjectConfig: 更新后的配置

        Raises:
            ConfigError: 配置更新失败时抛出
        """

        # 递归更新配置
        def recursive_update(current, updates):
            for key, value in updates.items():
                if key in current and isinstance(value, dict) and isinstance(current[key], dict):
                    recursive_update(current[key], value)
                else:
                    current[key] = value

        # 更新配置
        recursive_update(self.config, config_updates)

        # 验证新配置
        self.validate_config()

        # 保存配置
        self.save_config()

        return self.config

    def validate_config(self) -> None:
        """
        验证配置的完整性和正确性

        Raises:
            ConfigError: 配置验证失败时抛出
        """
        try:
            self._validate_config_structure(self.config, self.REQUIRED_CONFIG_FIELDS)
            self._validate_paths()
        except Exception as e:
            raise ConfigError(f"配置验证失败: {str(e)}")

    def _validate_config_structure(self, config: Dict[str, Any], required: ValidationStructure) -> None:
        """
        递归验证配置结构

        Args:
            config: 要验证的配置
            required: 必需的配置结构

        Raises:
            ConfigError: 配置结构验证失败时抛出
        """
        for key, value_type in required.items():
            if key not in config:
                raise ConfigError(f"缺少必需的配置项: {key}")

            if isinstance(value_type, dict):
                if not isinstance(config[key], dict):
                    raise ConfigError(f"配置项类型错误: {key} 应为字典")
                self._validate_config_structure(config[key], value_type)
            elif not isinstance(config[key], value_type):
                raise ConfigError(f"配置项类型错误: {key} 应为 {value_type.__name__}")

    def _validate_paths(self) -> None:
        """
        验证配置中的路径

        Raises:
            ConfigError: 路径验证失败时抛出
        """
        project_dir = Path(self.config["project"]["directory"])
        if not project_dir.exists():
            raise ConfigError(f"项目目录不存在: {project_dir}")

        dockerfile = project_dir / self.config["image"]["dockerfile"]
        if not dockerfile.exists():
            raise ConfigError(f"Dockerfile不存在: {dockerfile}")

        compose_file = project_dir / self.config["container"]["compose_file"]
        if not compose_file.exists():
            raise ConfigError(f"Docker Compose文件不存在: {compose_file}")

    def save_config(self) -> None:
        """
        保存配置到文件

        Raises:
            ConfigError: 配置保存失败时抛出
        """
        try:
            config_file = os.path.join(self.project_dir, "config.json")
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            raise ConfigError(f"保存配置失败: {str(e)}")

    def get_config(self) -> DefaultProjectConfig:
        """
        获取当前配置

        Returns:
            DefaultProjectConfig: 当前配置
        """
        return self.config
