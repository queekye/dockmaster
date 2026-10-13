# 来源与许可

本仓库的自有代码由 Kang Chen / queekye 开发，采用根目录 MIT 许可。
这次补充许可依据：现有 Git 作者记录均对应仓库所有者；dockmaster 原 README 和包元数据已声明 MIT。
GPU 模板来自同一作者的 [deeplearning-docker](https://github.com/queekye/deeplearning-docker)，
整合来源提交、文件哈希和修改原因记录在模板的 SOURCE_MANIFEST.json 中。

MIT 许可只覆盖本仓库自有文件，不替代镜像、操作系统或 Python 依赖的许可。
PyTorch 基础镜像、Ubuntu/系统软件、OpenSSH、Jupyter、MLflow 和 requirements.txt 中的包
均需遵循各自的原许可和通知；本仓库没有重新授权这些依赖，也没有分发其源码、镜像或模型权重。
使用者发布衍生镜像时，应保留随镜像安装的第三方许可文件，并核对所选版本的许可。
