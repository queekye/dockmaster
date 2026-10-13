# GPU 开发容器模板

此模板提供 PyTorch、JupyterLab、可选 SSH 和内部 MLflow；研究训练代码请另外克隆。
它来自 deeplearning-docker 的 modern-train 阶段，后续主线为
[dockmaster/templates/gpu](https://github.com/queekye/dockmaster/tree/main/templates/gpu)。

## 环境与运行

使用 Linux Docker Engine、Docker Compose v2、NVIDIA 驱动和 NVIDIA Container Toolkit。
主机必须能访问 PyTorch 基础镜像、apt 和 PyPI；构建时下载系统/Python 依赖，镜像较大。
requirements.txt 保留原研究环境的依赖范围，没有宣称版本锁定或论文结果可复现。
没有附带数据、模型、权重、私钥、密码或现有 Docker 状态。

```bash
cd templates/gpu                       # dockmaster 克隆中的目录
+# 在旧仓库对应 docker_projects/modern-train；后续使用 dockmaster 主线
bash start_service.sh --check           # 无 Docker 的安全配置预检
docker compose config                  # 校验本地 Compose 展开结果
docker compose build
docker compose up -d
docker compose exec -u developer modern-train jupyter server list
```

Jupyter 默认仅发布到主机 `127.0.0.1:21888`，保留自动生成令牌认证；最后一条命令
显示访问地址，只在自己的终端使用，令牌不要放入 Git 或共享日志。
远程服务器可通过 `ssh -L 21888:127.0.0.1:21888 user@server` 使用主机 SSH 转发。
不要为了远程访问直接把端口改成公网地址。需要团队访问时自行配置认证、TLS 和访问控制代理。

`gpu-workspace` 是持久化 named volume，容器里的 `/workspace` 归 developer 用户使用。
数据可另外通过 Compose override 将必要数据目录只读挂载到 `/datasets`。
主机路径必须实际存在且接收人的 Docker 可读取；不依赖作者个人目录。
备份该 volume 和自己写入的训练代码；`docker compose down` 不删除 volume，
`docker compose down -v` 会删除 volume，确认已备份再使用。

## 可选容器 SSH 与 MLflow

SSH 默认关闭；没有 root 登录或密码认证，没有在镜像构建时生成的客户端私钥。
可选 SSH 使用自己的客户端密钥，**只把对应公钥文件**只读挂载给容器：

```bash
export SSH_AUTHORIZED_KEYS_PATH="$HOME/.ssh/gpu_authorized_keys"
# 先将需要访问者的公钥写入该文件；文件不能是私钥，也不要提交到 Git。
docker compose -f docker-compose.yml -f docker-compose.ssh.yml config
docker compose -f docker-compose.yml -f docker-compose.ssh.yml up -d
ssh -p 21022 -L 16006:127.0.0.1:6006 developer@127.0.0.1
```

每个新容器在启动时生成独立 SSH **主机**密钥，重建容器后主机指纹会变化，需核对后更新 known_hosts。
Dockerfile 的 apt 安装可能创建主机密钥，已经在同一 RUN 层中移除，镜像不包含共享身份。
SSH 发布端口仍限主机 loopback；Jupyter 和 MLflow 以非 root 用户运行。
SSH override 同时启用 MLflow，MLflow 只绑定**容器内** `127.0.0.1:6006`，
不由 Compose 发布端口。通过上面的容器 SSH 转发访问 `http://127.0.0.1:16006`。
MLflow 此处没有登录认证；不要增加公网映射，实验数据库/工件保存在 workspace volume。

## 检查范围与后续

已验证配置约束、Shell 语法、预检失败分支和模拟服务启动/退出；这些检查不启动 Docker。
尚未实际构建镜像、运行 GPU、验证 SSH 公钥登录或全部研究依赖安装。
正式使用前在自己的临时 Docker 环境完成 build/up、Jupyter 登录、volume 重启保存和可选 SSH 验证。
后续优先拆分通用基础依赖/研究可选依赖、生成经构建验证的锁文件、加入隔离 Docker 集成测试。


## MLflow 安全最低版本

Dockerfile 要求 MLflow >= 3.5，不使用旧的 major-version 上限。
MLflow 官方说明 3.5.0 起默认 FastAPI/uvicorn 服务包含 Host/CORS 等安全中间件：
[官方网络安全说明](https://mlflow.org/docs/latest/self-hosting/security/network/)。
本模板保留其默认安全设置，不传 `--disable-security-middleware`，仍默认关闭 MLflow，
开启后只监听容器 loopback。此最低版本不是完整依赖锁或全部依赖漏洞审计；构建验证后再锁定实际版本。
