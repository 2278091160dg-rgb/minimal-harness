# 贡献指南

[English contribution guide](CONTRIBUTING.md) · [文档目录](docs/README.zh-CN.md)

感谢你帮助改进 Minimal Harness。

## 项目边界

核心是使用 Python 3.9+ 标准库实现的小型验收工具。改动应保留以下约束：

- Git 或证据无法可靠验证时拒绝完成。
- 确定性的命令执行，不通过 shell 解释命令。
- 运行时不引入第三方依赖。
- 支持 Linux、macOS 和 Windows。
- 保留已有 CLI 退出码约定。

需要平台 API 或额外工具的可选集成应放在 `template/.harness/` 之外。

## 开发流程

1. 重大行为或 schema 改动先开 issue 说明需求。
2. 改变行为前，先添加能复现问题的失败回归测试。
3. 每个提交聚焦一件事，解释涉及安全边界的取舍。
4. 运行完整检查：

```bash
python3 -m unittest discover -s tests -v
node --test examples/todo/test.mjs
python3 -m pip install ruff==0.15.12
ruff check --no-cache template/.harness integrations/github/publish_check.py scripts tests examples/quickstart
python3 template/.harness/harness.py --workspace template doctor
python3 template/.harness/harness.py --workspace examples/todo doctor
python3 template/.harness/harness.py --workspace examples/todo run check
```

浏览器相关改动还必须通过 `python3 tests/run_todo_walkthrough.py`，在临时项目中运行
真实 Chromium 验收和完整 Harness 任务流程。浏览器依赖的安装方法见
[首页](README.zh-CN.md)。

修改发布包时，还需针对固定提交执行：

```bash
python3 scripts/check_release.py --ref HEAD --version v0.0.0-ci --output-dir dist/release-smoke
```

此命令检查已提交的 ref，不包含尚未提交的编辑。版本号只是本地文件标签，不代表已
发布新版本。脚本检查 ZIP 摘要、许可证安装、验收、全部报告格式、代码变化后的过期
拒绝与恢复、完成和交接。CI 针对检出的提交执行同一检查；失败诊断只含脚本生成的示例项目。

## 用户文档

修改行为时同步更新中英文用户页面，按影响范围检查两版能力清单、示例和命令参考。
将尚未发布的行为与已发布版本下载步骤分别标明。对照 CLI 核查命令，并实际执行有
变化的示例；不需要为普通说明文字编写源文本匹配测试。
内部带日期的设计和研究资料无需完整翻译。根目录和运行时发行包中的 MIT 英文许可
文本应保持一致。

## 安全报告

包含漏洞或可用复现步骤的报告不要公开发到 issue；请遵循
[安全策略](SECURITY.zh-CN.md)。

提交贡献即表示你同意该贡献可以按本仓库的 MIT License 分发。
