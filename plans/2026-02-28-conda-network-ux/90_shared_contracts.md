# 共享契约冻结文档（唯一接口真相源）

## Goal
- 冻结跨 Agent 的公共接口和字段，作为唯一真相源，确保并行开发期间无歧义。

## In Scope
- 冻结 tool 名称、参数 schema、核心返回字段。
- 冻结 CLI 命令签名与参数语义。
- 冻结新增环境变量及默认值。
- 定义契约变更流程。

## Out of Scope
- 不描述实现细节和代码结构。
- 不承载测试用例细节（见 `04_agent_d_tests_integration.md`）。

## Files To Touch
- 本文件（`plans/2026-02-28-conda-network-ux/90_shared_contracts.md`）
- 契约变更涉及的实现文件（由对应 Agent 处理）

## Interfaces/Contracts
- Tool 接口（新增）：
  - `list_builtin_networks`
    - args: `query?: string`, `max_results?: int (1..200, default=20)`
    - returns: `ToolResult.data.network_catalog: list[object]`
  - `get_current_network_info`
    - args: 无（空模型）
    - returns: `ToolResult.data.current_network: object`
- Tool 接口（增强）：
  - `load_builtin_network(case_name: string)`
    - unknown case 时：
      - `ok=false`
      - `data.suggestions: list[string]`（最多 5 个）
      - `message` 包含下一步建议（查询可选网络）
- CLI 接口（新增）：
  - `agent networks [--query <kw>] [--max <n>] [--format table|json]`
  - `agent use <case_name>`
  - `agent tools [--format table|json]`
- ToolResult.data 字段标准（新增）：
  - `network_catalog`
    - 推荐元素字段：`name`（必填）, `doc`（可选）, `category`（可选）
  - `current_network`
    - 推荐字段：`name`, `bus_count`, `line_count`, `load_count`, `sgen_count`, `gen_count`
  - `suggestions`
    - `list[str]`, 按相似度降序，最多 5 项
- 新参数模型（新增）：
  - `ListBuiltinNetworksArgs`
  - `GetCurrentNetworkInfoArgs`
- 新环境变量（新增）：
  - `STARTUP_SHOW_NETWORKS=true`
  - `STARTUP_NETWORK_PREVIEW_COUNT=8`

## Implementation Steps
1. 首次开发前由 B/C/A/D 同步确认本文件内容。
2. 各 Agent 实施时严格按本文件字段和命名编码/编写文档/写测试。
3. 集成前由 D 按本文件逐条做契约一致性检查。

## Acceptance Criteria
- 所有新增命令、工具、参数名与本文件逐字一致。
- 测试断言字段名与本文件一致，无拼写分叉。
- README、CLI help、tool schema 不出现三份不一致定义。

## Risks & Mitigations
- 风险：并行开发时出现“先改代码后改契约”。
  - 缓解：强制流程为“先改契约文档，再改实现”。
- 风险：字段冗余扩张导致接口不稳定。
  - 缓解：新增字段必须保持向后兼容，删除字段需显式版本说明。
- 风险：命令别名引发行为歧义。
  - 缓解：本阶段不引入别名，仅保留冻结签名。

## Handoff Output
- 可被 A/B/C/D 共用的稳定接口清单。
- 契约检查结果记录（通过/偏差点）。
- 若有偏差，提供“契约修订提案 + 影响范围”。
