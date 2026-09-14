# 实战使用指南

[English](usage-guide.md) · [README](../README.zh-CN.md) ·
[CLI 参考](cli-reference.zh-CN.md) · [文档索引](README.zh-CN.md)

下面四个案例使用 schema v3，并从当前源码检出运行；`examples/quickstart` 与
`examples/todo` 不在已发布运行时 ZIP 中。v0.2.0-beta.1 运行时支持同一套 v3 基本流程，
当前源码还包含未发布加固，并会安装 `.harness/LICENSE`。

项目安装后，从项目根目录运行 `python3 .harness/harness.py ...`。从别处调用模板时，
全局 `--workspace PATH` 要写在子命令之前。省略它时，工作区是脚本所在目录的上级目录，
不是 shell 当前目录。相对 `--from` 则以 shell 当前目录解析。

## 案例一：发现并修复命令行回归

从源码仓库根目录复制已有 greeting 夹具：

```bash
mkdir ../harness-regression-demo
cp -R examples/quickstart/src examples/quickstart/tests examples/quickstart/greeting.task.json ../harness-regression-demo/
python3 template/.harness/harness.py --workspace ../harness-regression-demo init --agent codex
cd ../harness-regression-demo
git init
python3 .harness/harness.py doctor
python3 .harness/harness.py task add --from greeting.task.json
python3 .harness/harness.py next
```

默认策略已经覆盖所需范围：

```json
"allowed_paths": ["src/**", "tests/**", ".harness/**"]
```

源码夹具中的完整任务定义是：

```json
{
  "id": "greeting",
  "title": "有名字时问候指定用户，没有名字时使用默认值",
  "acceptance": [{
    "id": "greeting-cli",
    "type": "command",
    "instruction": "有参数时问候 Ada，无参数时问候 world。",
    "command": ["{python}", "tests/check_greeting.py"],
    "timeout_seconds": 30
  }]
}
```

在一次性副本中制造回归并运行验收：

```bash
python3 -c "from pathlib import Path; p=Path('src/greet.py'); p.write_text(p.read_text(encoding='utf-8').replace('Hello', 'Hi'), encoding='utf-8')"
python3 .harness/harness.py verify greeting
```

检查会打印 `Expected 'Hello, Ada!'` 不匹配信息。`verify` 返回 1，检查状态为 `failed`，
不能完成。即使配置了 `run check`，它也只是项目辅助检查，不能替代这条任务验收。

修正并重新运行：

```bash
python3 -c "from pathlib import Path; p=Path('src/greet.py'); p.write_text(p.read_text(encoding='utf-8').replace('Hi', 'Hello'), encoding='utf-8')"
python3 .harness/harness.py verify greeting
python3 .harness/harness.py report greeting --format text
python3 .harness/harness.py complete greeting
python3 .harness/harness.py handoff
```

预期依次看到 `PASS: named and default greetings match the CLI contract`、
`greeting [in_progress] — ready` 与 `Completed greeting`。`verify` 会写入受限日志、
attempt、证据、任务状态和交接；`report` 只读。

要观察新鲜度门禁，可在通过 `verify` 后、`complete` 前再改 `src/greet.py`。
`report greeting` 和 `complete greeting` 会以 1 退出并说明源码已过期。恢复后必须重跑
`verify greeting`。

## 案例二：浏览器截图验收

源码仓库内置完整的一次性 Todo 演练。它启动自己拥有的本地服务，通过 Playwright 驱动
真实 Chromium，检查新增、勾选、刷新持久化，保存真实截图，记录每次观察，并完成三个任务：

```bash
python3 -m pip install playwright
python3 -m playwright install chromium
python3 tests/run_todo_walkthrough.py
```

端口 8000 必须空闲。成功时最后会出现 `PASS: add, toggle, and reload persistence
verified` 与 `BROWSER_PROOF_DIRECTORY=...`。这些结果只对那一次实际运行有效，因为辅助脚本
确实执行并断言了浏览器动作。源码文件存在、截图存在或本文写出了预期，都不能证明浏览器试验
已经发生。

如果要用自己的浏览器工具执行，可从已有 Todo 夹具创建一次性项目。从源码仓库根目录复制应用，
初始化空状态，并装入示例已有的命令/策略配置。这个手动流程还需要 Node.js 执行 `run check`，
并需要能把截图保存到项目内的浏览器工具：

```bash
mkdir ../harness-todo-manual
cp -R examples/todo/site examples/todo/test.mjs ../harness-todo-manual/
python3 template/.harness/harness.py --workspace ../harness-todo-manual init --agent codex
cp examples/todo/.harness/config.json ../harness-todo-manual/.harness/config.json
cd ../harness-todo-manual
git init
mkdir -p .harness/specs .harness/artifacts
python3 .harness/harness.py doctor
```

把下面的最小定义保存为 `.harness/specs/todo-add.json`：

```json
{
  "id": "todo-add",
  "title": "新增一条未完成待办",
  "acceptance": [{
    "id": "add-in-browser",
    "type": "browser",
    "instruction": "新增待办后出现一条同文案且未勾选的项目。",
    "steps": [
      "打开 http://127.0.0.1:8000。",
      "输入 验证 Harness，点击 新增待办。",
      "观察到唯一同文案项目，并确认复选框未勾选。"
    ]
  }]
}
```

使用 Todo 策略把应用文件纳入范围：

```json
"allowed_paths": ["site/**", "test.mjs", "proof/**", ".harness/**"]
```

添加并领取，在终端 1 启动配置的服务：

```bash
python3 .harness/harness.py task add --from .harness/specs/todo-add.json
python3 .harness/harness.py next
python3 .harness/harness.py run check
python3 .harness/harness.py run start
```

`run check` 执行 Node 测试，但不创建任务验收。`run start` 一直占用前台，直到被停止。
在终端 2 使用浏览器工具逐步执行定义，并把工具实际产生的截图保存为
`.harness/artifacts/todo-add.png`。确认它是项目内真实、非空、非符号链接的普通文件。
只有实际观察到要求的结果后，才能记录：

```bash
python3 .harness/harness.py record todo-add add-in-browser --result passed \
  --summary "输入 验证 Harness，点击新增待办，实际观察到唯一同文案且未勾选的项目。" \
  --tool playwright \
  --artifact .harness/artifacts/todo-add.png
python3 .harness/harness.py report todo-add
python3 .harness/harness.py complete todo-add
```

成功记录会输出 `Recorded todo-add/add-in-browser: passed`。如果没有浏览器工具或有效截图，
应如实记录限制：

```bash
python3 .harness/harness.py record todo-add add-in-browser --result unverified \
  --summary "浏览器工具不可用，未执行验收步骤。"
```

该命令返回 1，完成门保持关闭。browser passed 还必须有 `--tool` 和至少一个
`--artifact`；多个附件重复写该选项。Harness 把观察与附件摘要绑定到当前源码，但不会独立
判断观察是否真实。

## 案例三：修订需求并重新验证

新建一个 greeting 示例，按案例一添加、领取并验证原定义。在完成之前，创建
`.harness/specs/greeting-v2.task.json`，内容为完整替换定义：

```bash
mkdir -p .harness/specs
```

```json
{
  "id": "greeting",
  "title": "还要精确问候 Grace",
  "acceptance": [{
    "id": "grace-cli",
    "type": "command",
    "instruction": "greet('Grace') 必须精确返回 Hello, Grace!",
    "command": [
      "{python}",
      "-B",
      "-c",
      "from src.greet import greet; assert greet('Grace') == 'Hello, Grace!'"
    ],
    "timeout_seconds": 30
  }]
}
```

默认 `.harness/**` 已覆盖 `.harness/specs/**`。修订并查看失效结果：

```bash
python3 .harness/harness.py task revise greeting \
  --from .harness/specs/greeting-v2.task.json \
  --note "验收现在明确指定 Grace"
python3 .harness/harness.py status
python3 .harness/harness.py report greeting
```

修订输出 `Task revise: greeting`。状态显示 `grace-cli [unverified]`；报告返回 1 并建议
重新验证。修订保留任务开始时的 Git/策略基线，把旧定义写入修订历史，也不会扩大
`allowed_paths`。

运行新检查并完成：

```bash
python3 .harness/harness.py verify greeting
python3 .harness/harness.py report greeting --format json
python3 .harness/harness.py complete greeting
```

内联命令返回 0，JSON 报告包含 `"ready": true` 和 `"exit_code": 0`，随后完成成功。
定义 ID 必须仍是 `greeting`。done 任务不能修订；blocked 任务必须先解阻，修订不能绕过失败阈值。

## 案例四：中断、阻塞与新会话恢复

本案例同时包含 command 和 manual 验收。在一个全新初始化的 Git 项目中，创建
目录与内容为 `not-ready` 的 `src/ready.txt`：

```bash
mkdir -p src .harness/specs
python3 -c "from pathlib import Path; Path('src/ready.txt').write_text('not-ready\n', encoding='utf-8')"
```

再把完整定义保存到
`.harness/specs/recovery.task.json`：

```json
{
  "id": "recovery",
  "title": "恢复就绪标记并人工检查",
  "acceptance": [
    {
      "id": "ready-command",
      "type": "command",
      "instruction": "src/ready.txt 的内容精确为 ready。",
      "command": [
        "{python}",
        "-c",
        "from pathlib import Path; assert Path('src/ready.txt').read_text(encoding='utf-8').strip() == 'ready'"
      ],
      "timeout_seconds": 30
    },
    {
      "id": "ready-manual",
      "type": "manual",
      "instruction": "人工打开 src/ready.txt，并实际看到 ready。",
      "steps": ["打开 src/ready.txt。", "观察去除首尾空白后的完整内容为 ready。"]
    }
  ]
}
```

默认 `allowed_paths` 覆盖 `src/**` 和 `.harness/**`。添加并领取：

```bash
python3 .harness/harness.py task add --from .harness/specs/recovery.task.json
python3 .harness/harness.py next
```

要单独演练中断，可暂时把 command 修订为
`["{python}", "-c", "import time; print('started', flush=True); time.sleep(300)"]`，
运行 `verify recovery`，在命令仍运行且尚未超时时按 Ctrl-C。`verify` 会在子进程停止后
才显示捕获的输出，因此不要等待终端出现 `started`。Harness 返回 130，检查保持
unverified，不能完成。继续前用 `task revise ... --note ...` 恢复上面的正式定义。

保持 `src/ready.txt` 为 `not-ready`，连续执行正式检查三次：

```bash
python3 .harness/harness.py verify recovery
python3 .harness/harness.py verify recovery
python3 .harness/harness.py verify recovery
python3 .harness/harness.py status
python3 .harness/harness.py handoff
```

每次验证都返回 1。默认阈值下第三次会把任务置为 `blocked`；此时 `next`、再次
`verify`、修订和完成都会被拒绝。失败与恢复命令会写入 `.harness/HANDOFF.md`。

修复文件、说明变化并重新验收：

```bash
python3 -c "from pathlib import Path; Path('src/ready.txt').write_text('ready\n', encoding='utf-8')"
python3 .harness/harness.py unblock recovery --note "检查连续失败后修正了就绪标记"
python3 .harness/harness.py verify recovery
```

现在由你本人打开 `src/ready.txt`。只有实际观察到 `ready` 时才记录 manual 结果；manual
不要求附件或工具名：

```bash
python3 .harness/harness.py record recovery ready-manual --result passed \
  --summary "已打开 src/ready.txt，实际观察到去除首尾空白后的完整内容为 ready。"
python3 .harness/harness.py report recovery
python3 .harness/harness.py complete recovery
python3 .harness/harness.py handoff
```

`unblock` 只重置失败计数并把 failed 检查变为 unverified，不会直接通过。随后 command
重验与实际 manual 观察共同提供两条通过证据。

新 Agent 或终端会话开始时运行：

```bash
python3 .harness/harness.py doctor
python3 .harness/harness.py status
sed -n '1,240p' .harness/HANDOFF.md
```

PowerShell 最后一行改为 `Get-Content .harness/HANDOFF.md`。`doctor` 只读；如果其余结构
有效但 passed 证据已过期，它返回 1。`status` 只读。`handoff` 才是重新生成会话摘要的显式写操作。

如果 `doctor`、`report` 或 `complete` 报告 `assume-unchanged` 或 `skip-worktree` index
标志，先检查受影响路径：

```bash
git ls-files -v -- path/to/affected-file
```

只有用户明确决定后，才让该路径重新出现在正常 Git 检查中：

```bash
git update-index --no-assume-unchanged -- path/to/affected-file
git update-index --no-skip-worktree -- path/to/affected-file
git status --short
git diff -- path/to/affected-file
```

检查刚暴露的改动。恢复不允许的改动，或为它新建范围合适的任务，再重新验证当前任务。不要删除
任务基线，也不要在任务进行中扩大已冻结策略来掩盖问题。

## 证据能证明什么

command 证据表明某个进程在一致的源码和验收快照上以什么状态退出，并保留受限日志。
browser/manual 证据表明操作者作出了声明，并保存经核验的附件元数据。源码 quickstart/Todo
自动演练属于工程证据，不能证明首次真人采用试验已经发生；真人试用仍在
[试用表](adoption-validation.zh-CN.md)中标记为 pending。
