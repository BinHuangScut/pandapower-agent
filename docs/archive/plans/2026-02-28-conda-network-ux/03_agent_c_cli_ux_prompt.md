# Agent C 工作单：CLI 体验与 Prompt 引导

## Goal
- 让用户通过命令行和自然语言两条路径都能方便地发现并切换 pandapower 内置网络。
- 提升首屏可发现性和任务可控性，减少“我不知道有哪些系统可选”的阻塞。

## In Scope
- 新增 CLI 子命令：`networks`, `use`, `tools`。
- chat 启动时主动展示网络预览（受配置控制）。
- 更新系统提示词，强化“网络查询请求优先走工具”行为。
- 调整 CLI 渲染，支持表格/json 输出的清晰展示。

## Out of Scope
- 不改动网络发现底层逻辑（由 B 提供）。
- 不改 README 与 conda 教程（由 A 负责）。
- 不主导新增测试文件（由 D 负责）。

## Files To Touch
- `src/app/main.py`
- `src/app/agent/prompts.py`
- `src/app/config.py`
- `src/app/agent/render.py`

## Interfaces/Contracts
- CLI 命令签名（冻结）：
  - `agent networks [--query <kw>] [--max <n>] [--format table|json]`
  - `agent use <case_name>`
  - `agent tools [--format table|json]`
- 依赖 B 提供工具：
  - `list_builtin_networks`
  - `get_current_network_info`
  - `load_builtin_network`
- 新增配置项（冻结）：
  - `STARTUP_SHOW_NETWORKS`（默认 `true`）
  - `STARTUP_NETWORK_PREVIEW_COUNT`（默认 `8`）

## Implementation Steps
1. 扩展 `argparse`：
   - 增加 `networks` 子命令及参数 `--query/--max/--format`。
   - 增加 `use <case_name>` 与 `tools --format` 子命令。
2. 实现命令处理：
   - `networks`：调用 `list_builtin_networks` 并渲染。
   - `use`：调用 `load_builtin_network`，成功后追加 `get_current_network_info` 回显。
   - `tools`：列出工具名、用途、关键参数（从 `TOOL_SPECS` 提取）。
3. chat 启动主动展示：
   - 若 `STARTUP_SHOW_NETWORKS=true`，展示前 `N` 个网络与提示语。
4. 更新 prompt：
   - 显式规则：用户询问可选网络时优先调用 `list_builtin_networks`。
   - 错误恢复规则：网络加载失败时向用户建议查询命令或再次调用网络列表工具。
5. 渲染优化：
   - `table` 输出人类友好；
   - `json` 输出便于自动化脚本。

## Acceptance Criteria
- `agent networks` 能输出可选网络，`--query` 和 `--max` 生效。
- `agent use case14` 成功并展示当前网络摘要。
- chat 首屏能看到网络预览提示（可通过配置关闭）。
- 自然语言“有哪些系统”场景在 tool trace 中出现 `list_builtin_networks`。

## Risks & Mitigations
- 风险：CLI 子命令与已有 `run/chat/reset` 逻辑冲突。
  - 缓解：保持子命令分发清晰，新增命令不修改原有命令语义。
- 风险：prompt 约束过强影响其他任务。
  - 缓解：规则限定触发条件为“网络可选性相关请求”。
- 风险：`tools` 命令输出与 schema 不一致。
  - 缓解：动态读取 `TOOL_SPECS`，避免手工维护两份描述。

## Handoff Output
- CLI 新命令实现与帮助文案。
- chat 首屏网络预览行为说明。
- prompt 变更 diff 与触发示例。
- `table/json` 两种输出样例。
