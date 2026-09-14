# 用户文档

[English documentation](README.md) · [项目首页](../README.zh-CN.md)

先阅读 [README](../README.zh-CN.md)，了解能力清单、版本选择、ZIP 独立目录安装，
并完整体验第一项任务。

| 下一步想做什么 | 对应指南 |
| --- | --- |
| 在 macOS 或 Windows 完成第一次体验 | [从这里开始](../START-HERE.zh-CN.md) |
| 用 Harness 修复 bug、记录浏览器观察、修订需求或接续会话 | [使用指南](usage-guide.zh-CN.md) |
| 查询命令、参数、前置状态、文件写入和退出码 | [命令参考](cli-reference.zh-CN.md) |
| 升级已有安装，同时保留原有状态 | [安装与迁移说明](../README.zh-CN.md) |
| 完成一次新用户试用并记录结果 | [真实新用户验证](adoption-validation.zh-CN.md) |
| 比较 Minimal Harness、completion gate 与更广的编排器 | [日期化竞品格局](research/2026-09-14-github-harness-landscape-refresh.md) |
| 开发或测试代码贡献 | [贡献指南](../CONTRIBUTING.zh-CN.md) |
| 私下报告漏洞、了解工具的信任边界 | [安全策略](../SECURITY.zh-CN.md) |
| 阅读软件许可证 | [MIT License 英文原文](../LICENSE) |

中英文使用指南对应同一组命令。命令名称、JSON 字段和状态值保持英文；终端输出和
自动生成的 Agent 指令暂未本地化。

## 版本范围

最新正式版是 **v0.1.1**；当前 schema v3 预发布版是 **v0.2.0-beta.2**，
包含 Git/runner 加固，运行时 ZIP 也包含 `.harness/LICENSE`。较早的 **v0.2.0-beta.1**
属于历史版本，缺少上述更新。请按照 README 的版本标识操作；源码示例与运行时 ZIP 分开提供。

## 维护者历史记录

[设计与实施计划](superpowers/plans/)、[设计规格](superpowers/specs/)、
[研究记录](research/) 和 [发布文案草稿](launch/) 都是带日期的维护记录，可能描述
过去的仓库可见性、发布状态或待办事项。安装时以 README 和当前
[发行版本页面](https://github.com/2278091160dg-rgb/minimal-harness/releases) 为准。
这些历史资料不是使用 Harness 的前置要求，也不逐篇翻译。
