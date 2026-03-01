# 多 Agent 主计划（Conda + Network Discovery UX）

## Goal
- 建立一个对新用户友好的 pandapower AI agent 交付路径：`conda` 可复现环境、可学习的 Get Started、可发现且可切换的内置网络、可验证的测试闭环。
- 为多 Agent 并行开发提供统一目标、统一接口边界、统一集成门禁，避免返工和接口漂移。

## In Scope
- 定义并冻结并行开发分工（A/B/C/D 四条工作流）。
- 定义跨 Agent 的共享契约（工具名、CLI 命令、结果字段、环境变量）。
- 定义里程碑、依赖顺序、验收口径和交接产物。
- 将关键测试场景前置为必测项。

## Out of Scope
- 本文件不直接实施代码变更。
- 不引入 Web UI、数据库持久化、权限系统。
- 不引入 conda-lock（当前阶段仅 `environment.yml`）。

## Files To Touch
- 本计划目录内文档（本文件与其余 7 个分工文件）。
- 代码实施阶段目标文件（由各 Agent 在其子计划中执行）：
  - `README.md`, `.env.example`, `environment.yml`
  - `src/app/power/tools.py`, `src/app/power/network_catalog.py`
  - `src/app/schema/tool_args.py`, `src/app/schema/types.py`
  - `src/app/main.py`, `src/app/agent/prompts.py`, `src/app/config.py`, `src/app/agent/render.py`
  - `tests/test_network_catalog.py`, `tests/test_cli_network_commands.py`, `tests/test_tool_network_discovery.py`, `tests/test_agent_loop.py`

## Interfaces/Contracts
- 接口真相源：`90_shared_contracts.md`。
- 冻结新增工具接口：
  - `list_builtin_networks(query?, max_results?)`
  - `get_current_network_info()`
- 冻结 CLI 公共接口：
  - `agent networks [--query --max --format]`
  - `agent use <case_name>`
  - `agent tools [--format]`
- 冻结结果字段标准：
  - `ToolResult.data.network_catalog`
  - `ToolResult.data.current_network`
  - `ToolResult.data.suggestions`

## Implementation Steps
1. `M1 合同冻结`：先完成并评审 `90_shared_contracts.md`，锁定接口命名、字段、参数。
2. `M2 并行开发`：
   - Agent B 与 Agent C 先对齐接口，再各自实现工具层与 CLI/Prompt。
   - Agent A 并行编写环境与上手文档。
   - Agent D 在 B/C 首版完成后补齐测试矩阵与回归验证。
3. `M3 集成验收`：
   - 使用 `99_integration_checklist.md` 执行集成前检查、集成后验证、发布门禁检查。
4. `M4 收尾交付`：
   - 汇总变更说明、示例命令、风险项与后续增量路线。

## Acceptance Criteria
- CLI 命令 `networks/use/tools` 可用且帮助信息清晰。
- LLM 在“有哪些系统/what networks”请求中能触发网络枚举工具。
- README 按冷启动路径可在 10 分钟内完成首次成功运行。
- 关键路径、错误路径、回归路径均有自动化测试覆盖并通过。

## Risks & Mitigations
- 风险：多 Agent 同时改动接口导致冲突。
  - 缓解：任何接口变更先更新 `90_shared_contracts.md`，再改代码。
- 风险：pandapower 内置网络列表提取不稳定。
  - 缓解：定义发现策略与回退策略，并为发现逻辑写单测。
- 风险：文档命令与实现不一致。
  - 缓解：集成门禁包含“README 命令逐条可执行”检查。
- 风险：CLI 与自然语言路径行为不一致。
  - 缓解：测试中强制覆盖命令行路径与 agent tool-calling 路径。

## Handoff Output
- 一套可直接执行的 4-Agent 分工文档。
- 一份冻结契约文档（唯一接口真相源）。
- 一份集成检查清单（上线前门禁）。
- 每个 Agent 的完成标准与交接格式定义。
