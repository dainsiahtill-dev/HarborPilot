## 现状结论
- 你给出的结论成立：
  - npm 命令执行链路存在可注入面：`filter_npm_commands()` 仅做 `startswith("npm ")`，`run_npm_commands()` 用 `shell=True`（[director_exec.py](file:///c:/Users/dains/Documents/Git/Harborpilot/modules/harborpilot-loop/director_exec.py#L476-L796)）。
  - 超时机制“部分存在但默认无效 + 仍有遗漏”：Director 的 `npm/tool` 子进程虽然接了 `state.npm_timeout`，但 `--npm-timeout` 默认 `0`（等同无超时，见 [loop-director.py](file:///c:/Users/dains/Documents/Git/Harborpilot/loops/loop-director.py#L1790-L1807)）；此外 `loop-pm.py` 拉起 Director、`director_memory.py` 的 lancedb_store、`server.py` 的 `ollama ps/stop` 都没 timeout（[loop-pm.py](file:///c:/Users/dains/Documents/Git/Harborpilot/loops/loop-pm.py#L192-L261)、[director_memory.py](file:///c:/Users/dains/Documents/Git/Harborpilot/modules/harborpilot-loop/director_memory.py#L87-L110)、[server.py](file:///c:/Users/dains/Documents/Git/Harborpilot/desktop/backend/server.py#L1213-L1275)）。
- README 同步：根 [README.md](file:///c:/Users/dains/Documents/Git/Harborpilot/README.md) 已覆盖“架构/产物/快速开始”，但仍存在不完整/不一致点：
  - 只读宣称与实际能力不一致：README 的 “UI Read-Only” 不变量（[README.md](file:///c:/Users/dains/Documents/Git/Harborpilot/README.md#L145-L147)）与后端提供的 PM/Director 启停、AGENTS 落地等写操作接口不匹配（[server.py](file:///c:/Users/dains/Documents/Git/Harborpilot/desktop/backend/server.py#L1281-L1467)）。
  - Reference 文档提到 `ui/pm-dashboard.py (Flet)` 但仓库仅有 `.pyc`，无源码（[reference.md](file:///c:/Users/dains/Documents/Git/Harborpilot/docs/reference.md#L9-L32)、[ui](file:///c:/Users/dains/Documents/Git/Harborpilot/ui)）。
  - `--run-npm` 的默认值在文档与代码也不一致：文档写默认 False（[reference.md](file:///c:/Users/dains/Documents/Git/Harborpilot/docs/reference.md#L98-L114)），代码实际 default=True。

## 修复目标
- 阻断“字符串拼接 + shell=True”导致的命令注入与链式执行。
- 给所有关键外部命令补上“合理默认超时 + 可配置覆盖”，避免 PM/Director/UI 因子进程卡死而整体挂起。
- 让 README/Reference 反映当前最新能力与默认参数，避免误导。

## 具体改动计划（会提交为一组可审阅的 patch）
### 1) 彻底修复 npm 命令注入面
- 修改 [director_exec.py](file:///c:/Users/dains/Documents/Git/Harborpilot/modules/harborpilot-loop/director_exec.py#L476-L796)：
  - `filter_npm_commands()` 从“前缀判断”升级为“解析 tokens + 严格校验”：
    - 使用 `shlex.split(..., posix=os.name != "nt")`；
    - 要求 `tokens[0]` 为 `npm`/`npm.cmd`（Windows）并拒绝空/异常输入；
    - 额外拒绝包含 `& | ; > <` 等高风险字符的原始输入（避免作为参数绕过/污染脚本）。
  - `run_npm_commands()` 改为 `subprocess.run(tokens, shell=False, ...)`，不再把用户/Planner 传来的字符串交给 shell 解释。

### 2) 让 npm timeout “默认有效”并对齐文档
- 修改 [loop-director.py](file:///c:/Users/dains/Documents/Git/Harborpilot/loops/loop-director.py)：
  - 将 `--run-npm` 默认值改为 **False**（与 docs/reference 一致，也更安全）；保留 `--run-npm/--no-run-npm` 显式开关。
  - 将 `--npm-timeout` 默认从 0 调整为一个合理值（例如 600s），并允许用环境变量覆盖（如 `HARBORPILOT_NPM_TIMEOUT`），仍支持显式传 0 表示“不设超时”。

### 3) 补齐遗漏的关键外部命令 timeout
- 修改 [loop-pm.py](file:///c:/Users/dains/Documents/Git/Harborpilot/loops/loop-pm.py#L192-L261)：
  - `run_director_once()` 外层 `subprocess.run` 增加 timeout（例如 `director_timeout + buffer`），并捕获 `TimeoutExpired` 写入 subprocess log + 返回明确退出码。
- 修改 [director_memory.py](file:///c:/Users/dains/Documents/Git/Harborpilot/modules/harborpilot-loop/director_memory.py#L87-L110)：
  - `invoke_lancedb_store()` 增加 timeout（默认例如 30~60s + env 可配），超时返回明确的 `LANCEDB_STORE_TIMEOUT`。
- 修改 [server.py](file:///c:/Users/dains/Documents/Git/Harborpilot/desktop/backend/server.py#L1213-L1275)：
  - `list_ollama_models()` 的 `ollama ps` 与 `ollama_stop()` 的 `ollama stop` 增加 timeout（默认例如 10~15s + env 可配），超时转为可读错误信息。
- 修改 [io_utils.py](file:///c:/Users/dains/Documents/Git/Harborpilot/modules/harborpilot-loop/io_utils.py#L666-L731) 与 [ports.py](file:///c:/Users/dains/Documents/Git/Harborpilot/modules/harborpilot-loop/ports.py#L37-L201)：
  - `where / powershell Get-Command / netstat` 等 `check_output` 增加短 timeout（例如 2~5s），并在超时/异常时走安全降级返回。

### 4) 修复后端子进程日志句柄泄漏
- 修改 [server.py](file:///c:/Users/dains/Documents/Git/Harborpilot/desktop/backend/server.py#L810-L825)：
  - `spawn_process()` 在 `Popen` 抛异常时确保关闭 `log_handle`，避免 Windows 句柄泄漏导致后续无法写/删日志。

### 5) 同步 README/Reference 到“最新能力与默认值”
- 更新 [README.md](file:///c:/Users/dains/Documents/Git/Harborpilot/README.md)：
  - 明确 Dashboard 的真实能力边界：UI 不直接改代码，但可以通过本地后端启动/停止 Loop、应用 AGENTS 等（并补充鉴权 token 说明）。
  - 增补一段“Dashboard 后端接口概览”（列出最关键的 `/pm/*`、`/director/*`、`/ws`、`/ollama/*`）。
- 更新 [docs/reference.md](file:///c:/Users/dains/Documents/Git/Harborpilot/docs/reference.md)：
  - 删除/修正 `ui/pm-dashboard.py (Flet)` 的过时描述；
  - 对齐 `--run-npm`、`--npm-timeout` 的默认值与含义。

## 验证方式（执行阶段会实际跑）
- Python：运行单测/静态检查（如项目已有 pytest）；并对关键模块做一次 `python -m compileall` 确认无语法问题。
- Desktop 前端：按现有约定跑 `npm run build:renderer` 与 `npx tsc -p frontend/tsconfig.json --noEmit`（见项目验证入口记忆）。
- 行为验证：构造恶意命令（例如包含 `&&`/`|`）确认被拒绝或被当作参数而不会链式执行；构造会挂起的外部命令模拟并确认 timeout 生效且日志可读。

如果你确认这个计划，我会按上述顺序落地代码与文档更新，并在最后给出每个修改点的 diff 导航链接与验证结果。