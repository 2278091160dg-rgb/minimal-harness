# 从这里开始：第一次使用 Minimal Harness

[English](START-HERE.md) · [项目 README](README.zh-CN.md)

这是一条给第一次使用者的短路径。你不需要先理解 Harness，也不需要 GitHub 账号、
模型 API 或 AI Agent。第一阶段预计 15 分钟；第二阶段可以再用 20 分钟尝试接入自己的
可丢弃项目副本。两套系统指引都固定使用 `v0.2.0-beta.2`。

## 先确认安全边界

- 只使用指引创建的示例目录，或你自己项目的**可丢弃副本**。
- 不要在生产项目、唯一副本或包含秘密信息的目录中试用。
- 本指引不会要求管理员权限，也不会让你删除目录。
- 开始前必须已经安装 Git 和 Python 3.9 或更高版本。系统页会先检查；检查不通过就停止。

## 选择你的系统

- [macOS：使用“终端”和 `python3`](docs/first-use-macos.zh-CN.md)
- [Windows 10/11：使用 PowerShell 和 `py -3`](docs/first-use-windows.zh-CN.md)

只打开与你系统对应的页面，不要混用两套命令。遇到和页面不一样的输出时，先停止，保留
终端最后 20 行，再告诉邀请你试用的人。失败也是有效反馈，不要手工修改 `.harness/`
里面的状态或证据文件。
