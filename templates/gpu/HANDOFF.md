# GPU 模板交接

## 当前情况

本目录是通用 GPU 开发容器，不含 modern-train 训练实现。来源：
`queekye/deeplearning-docker` 默认分支 `main`，整合前提交 `3b3588464de7fad6d242272392fedb07625c73b6`。
原来的 PyTorch 2.6/CUDA 12.4 基础环境和研究 requirements 已保留；改变了身份、端口、运行用户和默认计划。
环境配置、资源挂载、运行及安全边界见 [README.md](README.md)；逐文件来源见 [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json)。

## 有意调整

- 删除镜像内共享客户端私钥；安装自动生成的 SSH 主机密钥同层删除，运行时按容器生成。
- SSH 默认关闭，开启时强制使用只读公钥文件、禁止 root/密码认证。
- Jupyter 保留令牌，默认只发布主机 loopback；MLflow 默认关闭且只监听容器内部 loopback。
- 删除作者机器路径、帐号、历史 job_id 和自动推送/清理计划，config.json 作为无凭据示例。
- 移除 TLS trusted-host 绕过和机器专用镜像源；Jupyter/MLflow 以 developer 用户运行。
- 增加启动预检、子服务退出处理、Docker context 排除凭据和模型文件。

## 尚未完成及未来计划

没有做真实 Docker/GPU 集成测试，不能视作可直接部署的生产服务或论文实验锁定环境。
先完成 README 中的临时环境验收，再决定发布镜像；不要开启自动清理、自动推送或外部监听来代替验证。
研究代码、数据和模型由使用者另外提供，现有训练模型权重不属于此次整理内容。
来源仓库的历史分支由整理流程独立保留，当前源码迁移不改写旧 Git 历史。

MLflow 构建最低版本为 3.5，保留官方默认安全中间件；运行仍关闭/内部监听，参考 README 的官方来源。
