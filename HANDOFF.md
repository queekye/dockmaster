# dockmaster 交接

## 当前情况

项目提供 Docker 项目、镜像、容器和调度命令；自有主线前序提交为
`e8e387513e74a06ff75576693b9e565630f5cb62`。源码版本统一为 0.2.2，未向 PyPI 发布这个版本。
本次从同作者 deeplearning-docker 完整接入 [GPU 模板](templates/gpu/README.md)，
模板逐文件哈希/安全调整见 [SOURCE_MANIFEST.json](templates/gpu/SOURCE_MANIFEST.json)。

## 环境与操作

优先在 Linux 上用 Python 3.10+ 创建 venv；Docker 实际命令需要可访问的 Docker Engine 和 Compose v2。
执行 `python -m pip install -e .` 后，`dm --help`、`dockmaster --help` 或 `python -m dockmaster --help` 可查看入口。
源码安装避免 README 的旧 PyPI 版本与此次修改混淆。模板必须从源码目录使用；sdist 包含模板，wheel 只提供 Python CLI。
Windows 允许安装及 help/单元测试；python-daemon 后台调度只支持 POSIX，Windows 不提供守护进程调度。

初始化项目会接触 Docker 客户端；build/up/save/cleanup/schedule 均可能实际改变资源。
先在独立测试 Docker 主机验证，尤其是容器清理路径、备份/恢复与 scheduled job；勿直接对重要服务器执行。
仓库不附带作者机器目录、Docker 状态或已设置的定时任务，GPU 模板也不包含研究代码/数据/模型。
registry 凭据优先用 `docker login` 的凭据存储或 `DOCKER_PASSWORD` 环境变量；
不要放进命令行参数、config.json 或 Git。旧 config 的 password 字段保留兼容结构，CLI 忽略其非空值，保存时清空磁盘副本。

## 本次验证与限制

完成独立 venv 可编辑安装、三个 help 入口、Python AST 和 pytest 安全/配置/模拟推送测试；
GPU 模板完成 Shell 语法、配置预检与假服务启动/失败退出测试。所有测试没有实际 Docker 操作。
没有仓库原生 tests 目录（曾被 .gitignore 排除），这次加入的测试不等同全部生命周期覆盖。
未做 Docker/GPU 镜像构建、真实备份恢复、清理或后台调度集成验收，保持 Alpha 状态。

## 下一步

先建立隔离 Docker 集成 CI，覆盖含空格路径、备份前后数据和清理边界；然后核对旧配置格式，
统一 setup.py/setup.cfg 重复元数据，锁定一次实际构建通过的 GPU 依赖版本，再考虑发行版本/镜像。
历史阶段的 Git 分支与交接记录由组合整理流程保存；不要把旧仓库删除视为功能全部验证完成。


## 容器清理的范围

Compose 使用参数列表调用，不把项目文件路径解释为 shell 命令。
默认缓存清理仅针对 `/tmp/dockmaster` 和 `/var/cache/dockmaster`；不扫整个临时目录。
自定义路径必须是 `/tmp`、`/var/cache` 或 `/root/.cache` 下的明确子路径，
不支持 glob、父级跳转、根目录或数据目录。旧配置中的 `/tmp/*` 等必须改为明确路径。
删除前用容器内 `readlink -f --` 检查真实路径，拒绝指向缓存根以外的符号链接；
容器需提供兼容的 readlink/rm。无法解析或删除失败会报告失败，请先确认路径已建立。
执行清理时管理员需控制缓存目录，检查与删除之间不能被其他进程恶意替换链接。
这次只用假 Docker 验证上述边界，没有执行真实删除、备份或定时任务。
