# Docker项目和容器管理工具

一个通用的Docker环境管理工具，提供项目、镜像和容器生命周期管理，简化Docker环境的配置、使用和维护。

## 核心功能

- **项目管理**：创建、配置和管理Docker项目
- **镜像管理**：构建、标记、推送和清理Docker镜像
- **容器管理**：启动、停止、保存和监控容器
- **定时任务**：自动备份和清理，支持多种定时方案
- **状态监控**：实时查看项目、镜像和容器状态
- **资源优化**：智能清理和资源回收

## 当前维护状态

源码 Alpha 版本为 **0.2.2**，这次安全/整合改动尚未发布到 PyPI。
Linux Docker 环境是主要目标；Windows 支持安装和 help，后台调度需要 POSIX。
GPU 开发模板已由 deeplearning-docker 合并到 [templates/gpu](templates/gpu/README.md)。
请先阅读 [交接文档](HANDOFF.md) 的已验证范围和待完成事项；未宣称生产部署或真实 Docker 集成测试已通过。

## 安装

```bash
# 从PyPI安装最新版本
pip install dockmaster

# 旧 PyPI 版本不包含本次安全修复；本次优先源码安装

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
dm push [-r 仓库地址] [-u 用户名] [-t 标签] # 用 docker login 或环境变量提供密码
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
dm push -r registry.example.com -u username --prefix organization-name

# 推送镜像并使用 Docker 凭据存储或环境变量
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
      "paths": ["/tmp/dockmaster", "/var/cache/dockmaster"]
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
      "paths": ["/tmp/dockmaster", "/var/cache/dockmaster"]
    }
  }
}
```

## 敏感信息管理

为了避免在配置文件中明文存储敏感信息（如Docker仓库密码），工具支持使用环境变量来管理这些信息：

### 提供临时凭据

优先使用 `docker login` 配合 Docker credential helper。交互式临时密码也可以在隐藏输入中提供：

```bash
read -r -s -p "Registry password: " DOCKER_PASSWORD
printf '\n'
export DOCKER_PASSWORD
dm push -u username
unset DOCKER_PASSWORD
```

多个账户可以分别设置 `DOCKER_PASSWORD_USERNAME`（用户名大写），也应从隐藏输入或自己的凭据管理器注入。
不要把真实密码写进 shell 命令、`~/.bashrc`、`~/.profile`、config.json 或 Git。

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
   - 使用 `dm config` 配置仓库 URL/用户名；密码使用环境变量或 Docker 凭据存储
   - 先运行 `docker login`，再 `dm push -u 用户名`；不要把密码写在命令行或配置文件
   - 检查是否有推送权限
   - 对于私有仓库，确保仓库已创建

## 必需文件检查

工具会在初始化项目时检查以下必需文件：

- **Dockerfile**：用于构建镜像
- **docker-compose.yml**：用于管理容器

如果这些文件不存在，工具会提供以下选项：

1. 创建这些文件后再初始化
2. 使用 `--force` 参数强制初始化

## 凭据与验证

不要把 registry 密码写入 config.json/Git 或使用 `-p` 放入 shell 历史。
CLI 忽略旧的明文配置密码；保存配置时清空其磁盘副本。使用 Docker credential helper、
`docker login`、环境变量或隐藏输入提示。`--password` 只保留旧调用兼容。

```bash
python -m pip install -e . pytest
python -m pytest
dm --help
```

这些测试使用临时目录和假 Docker 客户端，不构建/推送/删除镜像、容器或运行后台计划。
真实 Docker 操作验收仍待完成，细节见 HANDOFF。

## 许可证

自有源码采用 [MIT](LICENSE)，依赖和模板来源见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。


## 容器清理的范围

Compose 使用参数列表调用，不把项目文件路径解释为 shell 命令。
默认缓存清理仅针对 `/tmp/dockmaster` 和 `/var/cache/dockmaster`；不扫整个临时目录。
自定义路径必须是 `/tmp`、`/var/cache` 或 `/root/.cache` 下的明确子路径，
不支持 glob、父级跳转、根目录或数据目录。旧配置中的 `/tmp/*` 等必须改为明确路径。
删除前用容器内 `readlink -f --` 检查真实路径，拒绝指向缓存根以外的符号链接；
容器需提供兼容的 readlink/rm。无法解析或删除失败会报告失败，请先确认路径已建立。
执行清理时管理员需控制缓存目录，检查与删除之间不能被其他进程恶意替换链接。
这次只用假 Docker 验证上述边界，没有执行真实删除、备份或定时任务。
