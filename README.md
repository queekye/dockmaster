# Docker项目和容器管理工具

一个通用的Docker环境管理工具，提供完整的项目、镜像和容器生命周期管理，简化Docker环境的配置、使用和维护。

## 核心功能

- **项目管理**：创建、配置和管理Docker项目
- **镜像管理**：构建、标记、推送和清理Docker镜像
- **容器管理**：启动、停止、保存和监控容器
- **定时任务**：自动备份和清理，支持多种定时方案
- **状态监控**：实时查看项目、镜像和容器状态
- **资源优化**：智能清理和资源回收

## 安装

```bash
# 从PyPI安装最新版本
pip install dockmaster

# 安装指定版本
pip install dockmaster==0.1.8

# 从源码安装
git clone https://github.com/queekye/dockmaster.git
cd dockmaster
pip install -e .
```

## 快速开始

```bash
# 在当前目录创建项目（目录名作为项目名）
dm init

# 或指定项目目录和名称
dm init /path/to/project -n my_project

# 强制初始化（即使缺少必需文件）
dm init -f
```

## 命令参考

### 基础命令

```bash
# 创建项目（默认使用当前目录）
dm init [目录] [-n 名称] [-f 强制]

# 构建镜像（默认使用当前目录的Dockerfile）
dm build [-f Dockerfile文件] [-p 推送] [--build-arg KEY=VALUE]

# 启动容器（默认使用docker-compose.yml）
dm up [-f compose文件]

# 停止容器
dm down

# 保存容器状态
dm save [-t 标签] [-c 清理]

# 推送镜像到远程仓库
dm push [-r 仓库地址] [-u 用户名] [-p 密码] [-t 标签]
```

### 配置命令

```bash
# 交互式配置（支持tab补全）
dm config

# 快速设置常用配置
dm config registry docker.io
dm config username myname
```

### 定时任务管理

```bash
# 交互式配置定时任务（支持多种执行频率）
dm schedule

# 快速设置备份任务（每天指定时间）
dm schedule backup "00:00"

# 快速设置清理任务（每天指定时间）
dm schedule cleanup "00:00"

# 列出所有定时任务
dm schedule list

# 删除定时任务（交互式选择）
dm schedule remove

# 删除指定类型的定时任务
dm schedule remove backup

# 管理调度器
dm schedule start   # 启动调度器
dm schedule stop    # 停止调度器
dm schedule restart # 重启调度器

# 查看调度器日志
dm schedule logs [-n 行数] [-f 持续显示]
dm schedule logs backup  # 查看备份任务日志
dm schedule logs cleanup # 查看清理任务日志
```

### 高级命令

```bash
# 构建并推送镜像（支持镜像前缀）
dm build -p --prefix organization-name

# 清理并保存容器
dm save -c

# 推送镜像到指定仓库（支持镜像前缀）
dm push -r registry.example.com -u username -p password --prefix organization-name

# 推送镜像并使用配置文件中的认证信息
dm push

# 查看状态
dm status

# 查看日志
dm logs [-f 持续显示]

# 清理旧镜像
dm cleanup [-d 天数] [-n 保留数量] [--dry-run]
```

## 环境配置示例

```yaml
# docker-compose.yml 示例
version: '3'
services:
  webapp:
    image: ${IMAGE_NAME:-my-webapp-image}:${TAG:-latest}
    container_name: ${CONTAINER_NAME:-my-webapp-container}
    environment:
      - NODE_ENV=production
    volumes:
      - ./data:/data
      - ./logs:/logs
    ports:
      - "8080:8080"
    restart: unless-stopped
```

## 配置文件

配置文件位于项目目录下的 `config.json`，可以通过 `dm config` 交互式配置：

```json
{
  "project": {
    "name": "my_project",
    "directory": "/path/to/project"
  },
  "image": {
    "name": "my-project-image",
    "dockerfile": "Dockerfile",
    "registry": {
      "url": "docker.io",
      "username": "username",
      "password": "",
      "prefix": "organization-name"
    }
  },
  "container": {
    "name": "my-project-container",
    "compose_file": "docker-compose.yml",
    "cleanup": {
      "paths": ["/tmp/*", "/var/cache/*"]
    }
  },
  "schedule": {
    "backup": {
      "type": "daily",
      "time": "00:00",
      "cleanup": false,
      "auto_push": false
    },
    "cleanup": {
      "type": "weekly",
      "weekday": "monday",
      "time": "00:00",
      "paths": ["/tmp/*", "/var/cache/*"]
    }
  }
}
```

## 敏感信息管理

为了避免在配置文件中明文存储敏感信息（如Docker仓库密码），工具支持使用环境变量来管理这些信息：

### 使用环境变量存储密码

1. **通用环境变量**：设置 `DOCKER_PASSWORD` 环境变量
   ```bash
   export DOCKER_PASSWORD="your_password"
   ```

2. **用户特定环境变量**：如果有多个用户，可以设置用户特定的环境变量
   ```bash
   # 假设用户名为 username
   export DOCKER_PASSWORD_USERNAME="your_password"
   ```

3. **持久化环境变量**：将环境变量添加到 `~/.bashrc` 或 `~/.profile` 文件中
   ```bash
   echo 'export DOCKER_PASSWORD="your_password"' >> ~/.bashrc
   source ~/.bashrc
   ```

## 定时任务管理

工具提供了强大的定时任务管理功能，支持多种执行频率和灵活的配置选项。

### 支持的定时任务类型

1. **每天执行**
   - 在指定时间执行任务
   - 格式：`HH:MM`

2. **每周执行**
   - 在指定的星期几和时间执行
   - 支持选择具体星期几
   - 格式：`星期几 HH:MM`

3. **每月执行**
   - 在每月指定日期和时间执行
   - 支持选择1-31号
   - 格式：`日期 HH:MM`

4. **每小时执行**
   - 在每小时的指定分钟执行
   - 格式：`分钟数(0-59)`

### 任务类型

支持以下类型的定时任务：

- **备份任务**：定期将容器保存为镜像
  - 可选择是否在备份前清理容器
  - 可选择是否自动推送备份镜像
  - 支持自定义备份镜像名称和标签

- **清理任务**：定期清理容器内的缓存文件
  - 可自定义清理路径
  - 支持多路径配置
  - 支持排除特定路径

### 调度器管理

- **状态监控**
  - 实时查看调度器运行状态
  - 查看任务执行历史
  - 监控任务执行时间

- **日志管理**
  - 分任务类型记录日志
  - 支持日志轮转
  - 支持实时日志查看

- **错误处理**
  - 自动记录任务执行错误
  - 失败重试机制
  - 异常通知

## 工作流最佳实践

1. **项目初始化**
   - 使用 `dm init` 创建项目结构
   - 配置适合您项目的Dockerfile和docker-compose.yml

2. **环境配置**
   - 使用 `dm config` 设置项目参数
   - 配置资源限制和环境变量

3. **开发周期**
   - 使用 `dm build` 构建开发环境
   - 使用 `dm up` 启动容器
   - 开发和测试
   - 使用 `dm save` 保存重要状态

4. **生产部署**
   - 使用 `dm build -p` 构建并推送生产镜像
   - 配置自动备份 `dm schedule backup`
   - 设置资源清理 `dm schedule cleanup`

5. **资源管理**
   - 定期使用 `dm status` 监控资源使用
   - 使用 `dm cleanup` 清理不需要的镜像
   - 使用 `dm logs` 排查问题

## 常见问题

1. **命令不生效**
   - 确保在正确的项目目录下
   - 检查配置文件是否正确
   - 使用 `dm status` 查看当前状态

2. **配置问题**
   - 使用 `dm config` 交互式配置
   - 检查配置文件格式
   - 使用环境变量覆盖敏感配置

3. **镜像构建失败**
   - 检查Dockerfile语法
   - 确保基础镜像可用
   - 查看构建日志 `dm logs`

4. **定时任务不执行**
   - 检查cron表达式格式
   - 确保系统时间正确
   - 查看任务列表 `dm schedule list`

5. **推送镜像失败**
   - 使用 `dm config` 配置正确的仓库信息（URL、用户名、密码）
   - 确保已登录到镜像仓库：`dm push -u 用户名 -p 密码`
   - 检查是否有推送权限
   - 对于私有仓库，确保仓库已创建

## 必需文件检查

工具会在初始化项目时检查以下必需文件：

- **Dockerfile**：用于构建镜像
- **docker-compose.yml**：用于管理容器

如果这些文件不存在，工具会提供以下选项：

1. 创建这些文件后再初始化
2. 使用 `--force` 参数强制初始化

## 许可证

MIT 