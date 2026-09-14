# macOS：15 分钟第一次成功体验

[English](first-use-macos.md) · [重新选择系统](../START-HERE.zh-CN.md)

本页已按 Minimal Harness `v0.2.0-beta.2` 编写。请打开 macOS 的“终端”，每次只复制
当前代码框。不要在生产项目中执行这些命令，也不要提前阅读完整 README。

## 1. 检查电脑是否可以参加试用

运行：

```bash
python3 --version
git --version
```

只有同时看到 Python `3.9` 或更高版本，以及一行 Git 版本时才继续。看到
`command not found`、Python 版本过低或其他错误时，请停止并把原文发给邀请人。本页不负责
安装系统依赖。

再运行：

```bash
test ! -e "$HOME/minimal-harness-first-use-source" && echo "source path ready"
test ! -e "$HOME/harness-demo" && echo "demo path ready"
```

必须同时看到 `source path ready` 和 `demo path ready`。少任何一行都停止；不要删除已有目录。

记录现在的开始时间。

## 2. 创建一次性示例

整段复制到终端：

```bash
cd "$HOME"
git clone --branch v0.2.0-beta.2 --depth 1 https://github.com/denggui-ai/minimal-harness.git minimal-harness-first-use-source
mkdir harness-demo
cp -R minimal-harness-first-use-source/examples/quickstart/src minimal-harness-first-use-source/examples/quickstart/tests minimal-harness-first-use-source/examples/quickstart/greeting.task.json harness-demo/
python3 minimal-harness-first-use-source/template/.harness/harness.py --workspace "$HOME/harness-demo" init --agent generic
cd "$HOME/harness-demo"
git init
```

最后应该看到 Git 初始化成功。如果任一命令显示错误，停止并保留终端最后 20 行。

## 3. 完成第一次验收

依次运行：

```bash
python3 .harness/harness.py doctor
python3 .harness/harness.py task add --from greeting.task.json
python3 .harness/harness.py next
python3 .harness/harness.py verify greeting
```

请找到这一行：

```text
PASS: named and default greetings match the CLI contract
```

没有看到 `PASS` 就停止。看到后先不要执行 `complete`。

## 4. 观察一次变化

运行下面两条命令。第二条可能返回非零；这正是要观察的结果，不要因此关闭终端。

```bash
python3 -c "from pathlib import Path; p=Path('src/greet.py'); p.write_text(p.read_text(encoding='utf-8').replace('Hello', 'Hi'), encoding='utf-8')"
python3 .harness/harness.py report greeting
```

先停下来，用你自己的话写一句：**刚才已经 PASS，为什么现在仍不能完成？**

不要搜索答案，也不要让 AI 解释。先把你的原话记下来，再继续。

## 5. 恢复并完成

```bash
python3 -c "from pathlib import Path; p=Path('src/greet.py'); p.write_text(p.read_text(encoding='utf-8').replace('Hi', 'Hello'), encoding='utf-8')"
python3 .harness/harness.py verify greeting
python3 .harness/harness.py report greeting
python3 .harness/harness.py complete greeting
python3 .harness/harness.py handoff
sed -n '1,160p' .harness/HANDOFF.md
```

应再次看到 `PASS`、包含 `ready` 的报告和 `Completed greeting`。看完交接文件后，再写一句：
**如果现在开启一个新会话，它应该先做什么？**

记录完成时间。第一阶段到这里结束。

## 6. 可选：接入你自己的项目副本

这部分只使用一个已经能运行测试的 Git 项目副本，而且测试命令运行前后的 `git status` 应该
不变。先在 Finder 复制整个项目，再在终端进入副本目录。不要使用原项目。运行 `pwd` 和
`git status`，确认路径确实是副本且 Git 可用。

在副本根目录整段运行下面的安装命令：

```bash
(
set -eu
mh_project="$PWD"
mh_version=v0.2.0-beta.2
mh_base="https://github.com/denggui-ai/minimal-harness/releases/download/$mh_version"
mh_stage="$(mktemp -d)"
curl -fL "$mh_base/minimal-harness-$mh_version.zip" -o "$mh_stage/minimal-harness-$mh_version.zip"
curl -fL "$mh_base/SHA256SUMS.txt" -o "$mh_stage/SHA256SUMS.txt"
if command -v sha256sum >/dev/null 2>&1; then
  (cd "$mh_stage" && sha256sum -c SHA256SUMS.txt)
else
  (cd "$mh_stage" && shasum -a 256 -c SHA256SUMS.txt)
fi
mkdir "$mh_stage/runtime"
python3 -m zipfile -e "$mh_stage/minimal-harness-$mh_version.zip" "$mh_stage/runtime"
python3 "$mh_stage/runtime/.harness/harness.py" --workspace "$mh_project" init --agent generic
)
python3 .harness/harness.py doctor
```

然后创建任务文件：

```bash
touch first-task.json
open -e first-task.json
```

如果这是 Python 项目，并且平时用 `python3 -m unittest discover` 测试，粘贴：

```json
{
  "id": "first-check",
  "title": "现有 Python 测试保持通过",
  "acceptance": [{
    "id": "project-tests",
    "type": "command",
    "instruction": "运行项目现有的 Python unittest 测试。",
    "command": ["{python}", "-B", "-m", "unittest", "discover"],
    "timeout_seconds": 300
  }]
}
```

如果这是 Node 项目，并且平时用 `npm test` 测试，改为粘贴：

```json
{
  "id": "first-check",
  "title": "现有 Node 测试保持通过",
  "acceptance": [{
    "id": "project-tests",
    "type": "command",
    "instruction": "运行项目现有的 npm 测试。",
    "command": ["npm", "test"],
    "timeout_seconds": 300
  }]
}
```

保存并关闭 TextEdit，然后运行：

```bash
python3 .harness/harness.py task add --from first-task.json
python3 .harness/harness.py next
python3 .harness/harness.py verify first-check
python3 .harness/harness.py report first-check
python3 .harness/harness.py complete first-check
python3 .harness/harness.py handoff
```

如果你的项目不属于这两种、没有现成测试命令，或者任何一步失败，请停止并记录原因。不要为了
让它通过而修改 `.harness/` 状态文件。

## 7. 把这六项发给邀请人

1. macOS 版本、`python3 --version`、`git --version` 和使用的中文页面。
2. 从开始到固定示例完成用了多久。
3. 第一个看不懂或卡住的位置；附终端最后 20 行原文。
4. 你对“PASS 后为什么仍不能完成”的原话。
5. 是否尝试了项目副本、结果如何、是否需要帮助。
6. 你是否愿意在真实项目再次使用；请写自己的理由。

不要发送密钥、私有源码或未经同意的截图。
