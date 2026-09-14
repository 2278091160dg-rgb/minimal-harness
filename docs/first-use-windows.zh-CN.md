# Windows：15 分钟第一次成功体验

[English](first-use-windows.md) · [重新选择系统](../START-HERE.zh-CN.md)

本页已按 Minimal Harness `v0.2.0-beta.2` 编写。请打开 Windows 10/11 的 PowerShell，
不要使用 CMD、Git Bash 或 WSL。每次只复制当前代码框。不要在生产项目中执行这些命令，
也不要提前阅读完整 README。

## 1. 检查电脑是否可以参加试用

运行：

```powershell
py -3 --version
git --version
```

只有同时看到 Python `3.9` 或更高版本，以及一行 Git 版本时才继续。看到无法识别命令、
Python 版本过低或其他错误时，请停止并把原文发给邀请人。本页不负责安装系统依赖。

再运行：

```powershell
Test-Path "$HOME\minimal-harness-first-use-source"
Test-Path "$HOME\harness-demo"
```

必须连续看到两个 `False`。出现任何 `True` 都停止；不要删除已有目录。记录现在的开始时间。

## 2. 创建一次性示例

整段复制到 PowerShell：

```powershell
Set-Location $HOME
git clone --branch v0.2.0-beta.2 --depth 1 https://github.com/2278091160dg-rgb/minimal-harness.git minimal-harness-first-use-source
New-Item -ItemType Directory -Path "$HOME\harness-demo" | Out-Null
Copy-Item -Recurse -Path "$HOME\minimal-harness-first-use-source\examples\quickstart\src","$HOME\minimal-harness-first-use-source\examples\quickstart\tests","$HOME\minimal-harness-first-use-source\examples\quickstart\greeting.task.json" -Destination "$HOME\harness-demo"
py -3 "$HOME\minimal-harness-first-use-source\template\.harness\harness.py" --workspace "$HOME\harness-demo" init --agent generic
Set-Location "$HOME\harness-demo"
git init
```

最后应该看到 Git 初始化成功。如果任一命令显示错误，停止并保留 PowerShell 最后 20 行。

## 3. 完成第一次验收

依次运行：

```powershell
py -3 .harness\harness.py doctor
py -3 .harness\harness.py task add --from greeting.task.json
py -3 .harness\harness.py next
py -3 .harness\harness.py verify greeting
```

请找到这一行：

```text
PASS: named and default greetings match the CLI contract
```

没有看到 `PASS` 就停止。看到后先不要执行 `complete`。

## 4. 观察一次变化

运行下面两条命令。第二条可能返回非零；这正是要观察的结果，不要因此关闭 PowerShell。

```powershell
py -3 -c "from pathlib import Path; p=Path('src/greet.py'); p.write_text(p.read_text(encoding='utf-8').replace('Hello', 'Hi'), encoding='utf-8')"
py -3 .harness\harness.py report greeting
```

先停下来，用你自己的话写一句：**刚才已经 PASS，为什么现在仍不能完成？**

不要搜索答案，也不要让 AI 解释。先把你的原话记下来，再继续。

## 5. 恢复并完成

```powershell
py -3 -c "from pathlib import Path; p=Path('src/greet.py'); p.write_text(p.read_text(encoding='utf-8').replace('Hi', 'Hello'), encoding='utf-8')"
py -3 .harness\harness.py verify greeting
py -3 .harness\harness.py report greeting
py -3 .harness\harness.py complete greeting
py -3 .harness\harness.py handoff
Get-Content .harness\HANDOFF.md
```

应再次看到 `PASS`、包含 `ready` 的报告和 `Completed greeting`。看完交接文件后，再写一句：
**如果现在开启一个新会话，它应该先做什么？**

记录完成时间。第一阶段到这里结束。

## 6. 可选：接入你自己的项目副本

这部分只使用一个已经能运行测试的 Git 项目副本，而且测试命令运行前后的 `git status` 应该
不变。先在文件资源管理器复制整个项目，再用 PowerShell 进入副本目录。不要使用原项目。运行
`Get-Location` 和 `git status`，确认路径确实是副本且 Git 可用。

在副本根目录整段运行下面的安装命令：

```powershell
$ErrorActionPreference = "Stop"
$Project = (Get-Location).Path
$Version = "v0.2.0-beta.2"
$Base = "https://github.com/2278091160dg-rgb/minimal-harness/releases/download/$Version"
$Stage = Join-Path ([IO.Path]::GetTempPath()) ("minimal-harness-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $Stage | Out-Null
$Zip = Join-Path $Stage "minimal-harness-$Version.zip"
$Sums = Join-Path $Stage "SHA256SUMS.txt"
Invoke-WebRequest "$Base/minimal-harness-$Version.zip" -OutFile $Zip
Invoke-WebRequest "$Base/SHA256SUMS.txt" -OutFile $Sums
$Expected = ((Get-Content $Sums | Where-Object { $_ -match "minimal-harness-$([regex]::Escape($Version))\.zip" }) -split '\s+')[0].ToLowerInvariant()
$Actual = (Get-FileHash $Zip -Algorithm SHA256).Hash.ToLowerInvariant()
if ($Actual -ne $Expected) { throw "SHA-256 mismatch: expected $Expected, observed $Actual" }
$Runtime = Join-Path $Stage "runtime"
Expand-Archive -Path $Zip -DestinationPath $Runtime
py -3 "$Runtime\.harness\harness.py" --workspace $Project init --agent generic
if ($LASTEXITCODE -ne 0) { throw "Minimal Harness init failed with exit $LASTEXITCODE" }
py -3 .harness\harness.py doctor
```

然后运行 `notepad first-task.json`。如果这是 Python 项目，并且平时用
`py -3 -m unittest discover` 测试，粘贴：

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

保存并关闭记事本，然后运行：

```powershell
py -3 .harness\harness.py task add --from first-task.json
py -3 .harness\harness.py next
py -3 .harness\harness.py verify first-check
py -3 .harness\harness.py report first-check
py -3 .harness\harness.py complete first-check
py -3 .harness\harness.py handoff
```

如果你的项目不属于这两种、没有现成测试命令，或者任何一步失败，请停止并记录原因。不要为了
让它通过而修改 `.harness/` 状态文件。

## 7. 把这六项发给邀请人

1. Windows 版本、`py -3 --version`、`git --version` 和使用的中文页面。
2. 从开始到固定示例完成用了多久。
3. 第一个看不懂或卡住的位置；附 PowerShell 最后 20 行原文。
4. 你对“PASS 后为什么仍不能完成”的原话。
5. 是否尝试了项目副本、结果如何、是否需要帮助。
6. 你是否愿意在真实项目再次使用；请写自己的理由。

不要发送密钥、私有源码或未经同意的截图。
