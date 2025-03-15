# Dockmaster 开发文档

## 项目结构

```
dockmaster/
├── dockmaster/           # 主代码目录
│   ├── __init__.py      # 包初始化文件
│   ├── __main__.py      # 入口文件
│   ├── cli.py           # CLI命令行接口
│   ├── interactive.py    # 交互式配置模块
│   ├── cli_utils.py     # CLI工具函数
│   ├── constants.py     # 常量定义
│   ├── utils.py         # 通用工具函数
│   ├── commands/        # 命令模块
│   ├── formatters/      # 格式化模块
│   └── managers/        # 管理器模块
│       ├── container/   # 容器管理相关模块
│       ├── project/     # 项目管理相关模块
│       └── image/       # 镜像管理相关模块
├── docs/                # 文档目录
├── tests/               # 测试目录
└── setup.py            # 安装配置文件
```

## 代码规范

1. 类型注解
   - 所有函数必须包含完整的类型注解（参数和返回值）
   - 使用`typing`模块中的类型
   - 复杂类型使用`TypeVar`或自定义类型

2. 日志规范
   - 使用`loguru`进行日志记录
   - 日志级别使用规范：
     - DEBUG: 调试信息
     - INFO: 操作信息
     - WARNING: 警告信息
     - ERROR: 错误信息
     - CRITICAL: 严重错误
   - 日志格式统一使用项目定义的格式

3. 错误处理
   - 使用自定义异常类
   - 在适当的层级处理异常
   - 提供有意义的错误信息

4. 代码风格
   - 遵循PEP 8规范
   - 使用中文注释
   - 类和函数必须包含文档字符串

## 开发指南

### 1. 环境设置

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# 安装依赖
pip install -r requirements.txt

# 安装开发依赖
pip install -r requirements-dev.txt
```

### 2. 开发流程

1. 创建功能分支
```bash
git checkout -b feature/your-feature
```

2. 开发新功能
   - 遵循代码规范
   - 添加单元测试
   - 更新文档

3. 提交代码
```bash
git add .
git commit -m "feat: 添加新功能"
```

4. 运行测试
```bash
pytest tests/
```

5. 提交PR
   - 描述功能变更
   - 关联相关issue
   - 等待review

### 3. 测试指南

1. 单元测试
   - 使用`pytest`框架
   - 测试文件命名：`test_*.py`
   - 每个模块都应该有对应的测试

2. 集成测试
   - 测试多个模块的交互
   - 模拟真实使用场景

3. 运行测试
```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_container.py

# 生成覆盖率报告
pytest --cov=dockmaster tests/
```

### 4. 文档维护

1. 代码文档
   - 使用文档字符串
   - 包含参数说明
   - 包含返回值说明
   - 包含异常说明

2. 项目文档
   - README.md: 项目概述
   - CONTRIBUTING.md: 贡献指南
   - CHANGELOG.md: 变更日志

### 5. 发布流程

1. 版本号规范
   - 遵循语义化版本
   - 格式：MAJOR.MINOR.PATCH

2. 发布步骤
   - 更新版本号
   - 更新CHANGELOG
   - 创建发布标签
   - 发布到PyPI

## 模块说明

### 容器管理模块

1. 基本操作
   - 启动容器
   - 停止容器
   - 保存镜像
   - 清理容器

2. 镜像操作
   - 构建镜像
   - 推送镜像
   - 标记镜像
   - 删除镜像

3. 调度功能
   - 创建定时任务
   - 管理任务
   - 查看任务状态

### 项目管理模块

1. 项目操作
   - 创建项目
   - 配置项目
   - 删除项目

2. 配置管理
   - 读取配置
   - 更新配置
   - 验证配置

## 常见问题

1. Docker连接问题
   - 检查Docker守护进程
   - 检查权限设置
   - 查看错误日志

2. 配置问题
   - 检查配置文件格式
   - 验证配置项
   - 使用默认配置

## 贡献指南

1. 提交PR
   - 遵循代码规范
   - 添加测试用例
   - 更新文档

2. 报告问题
   - 使用issue模板
   - 提供复现步骤
   - 附加错误日志

## 更新日志

### [0.1.0] - 2024-03-15

- 初始版本
- 基本功能实现
- 文档完善 