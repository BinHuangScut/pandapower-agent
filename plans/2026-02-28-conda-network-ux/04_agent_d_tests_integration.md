# Agent D 工作单：测试矩阵与集成门禁

## Goal
- 确保多 Agent 并行交付后可稳定集成，关键路径、错误路径、回归路径都可自动化验证。

## In Scope
- 新增网络目录与 CLI 子命令测试。
- 扩展 agent tool-calling 测试，覆盖“可选系统查询”场景。
- 建立集成门禁检查项并执行验证。

## Out of Scope
- 不主导实现文档和 CLI 功能（由 A/C 负责）。
- 不主导网络工具开发（由 B 负责）。
- 不改业务功能设计，仅做验证与问题回报。

## Files To Touch
- `tests/test_network_catalog.py`（新建）
- `tests/test_cli_network_commands.py`（新建）
- `tests/test_tool_network_discovery.py`（新建）
- `tests/test_agent_loop.py`（扩展）
- （可选）`tests/conftest.py`（若需共享 fixture）

## Interfaces/Contracts
- 以 `90_shared_contracts.md` 为断言依据：
  - 工具名、参数名、结果字段名必须一致。
  - CLI 命令签名必须一致。
- 关键断言：
  - `ToolResult.data.network_catalog` 类型与字段。
  - `ToolResult.data.current_network` 结构完整。
  - `ToolResult.data.suggestions` 在错误场景可用。

## Implementation Steps
1. `test_network_catalog.py`：
   - 测试发现列表非空并包含 `case14`。
   - 测试 query 过滤与 max_results 截断。
2. `test_tool_network_discovery.py`：
   - 测试 `list_builtin_networks` 工具返回结构。
   - 测试 `load_builtin_network` unknown case 时 suggestions。
   - 测试 `get_current_network_info` 有/无 net 行为。
3. `test_cli_network_commands.py`：
   - 测试 `agent networks` 默认输出。
   - 测试 `agent use case14` 成功路径。
   - 测试 `agent use wrong_name` 失败与建议提示。
4. `test_agent_loop.py` 扩展：
   - Mock 模型返回 `list_builtin_networks` 调用。
   - 验证 tool trace 中出现该工具并有合理输出。
5. 回归验证：
   - `run/chat/reset` 现有行为不退化。

## Acceptance Criteria
- 新增测试覆盖计划中的 7 个关键场景。
- 测试命名清晰，失败信息可定位到具体契约破坏点。
- 所有测试通过且无 flaky 行为。
- 回归路径通过（原有基础测试不退化）。

## Risks & Mitigations
- 风险：CLI 测试依赖终端输出格式，易脆弱。
  - 缓解：优先断言关键字段/关键字，不对齐空格与颜色控制符。
- 风险：pandapower 真实依赖导致测试慢。
  - 缓解：单测优先 mock，少量必要集成测试保留真实调用。
- 风险：多分支并行导致测试夹具不兼容。
  - 缓解：统一公共 fixture 与命名规范，按契约驱动断言。

## Handoff Output
- 完整测试报告（通过/失败列表）。
- 覆盖矩阵（场景 -> 测试文件 -> 断言点）。
- 若失败，提供最小复现与定位建议（文件/函数/字段）。
