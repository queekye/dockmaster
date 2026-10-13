# deeplearning-docker：已整合的 GPU 模板阶段

后续通用 Docker 工具与模板在 [queekye/dockmaster](https://github.com/queekye/dockmaster) 维护。
本项目的 `docker_projects/modern-train` 完整迁移至
[dockmaster/templates/gpu](https://github.com/queekye/dockmaster/tree/main/templates/gpu)，
不是 modern-train 研究训练源代码仓库。

本仓库保留阶段来源和交接信息；开始新开发请使用 dockmaster。
本阶段仍同步修复了共享 SSH 身份、root/密码登录和公开端口默认值，以免旧入口误导使用者。
具体环境、启动、资源路径、安全边界与待验收项目见 [模板 README](docker_projects/modern-train/README.md)
和 [交接文档](docker_projects/modern-train/HANDOFF.md)。
原 Git 历史不改写；迁移完整性和历史保存经确认后，仓库由整体整理流程决定退休。

自有文件采用 [MIT](LICENSE)；第三方依赖说明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
