# Agent B 工作单：Network Catalog 与 Tool 扩展

## Goal
- 让 pandapower 内置网络“可枚举、可过滤、可推荐”，并以工具接口形式稳定暴露给 agent 与 CLI。

## In Scope
- 新增网络目录发现模块。
- 在工具层新增网络查询与当前网络信息工具。
- 增强 `load_builtin_network` 错误体验（给近似候选）。
- 扩展工具参数 schema 与返回字段规范。

## Out of Scope
- 不负责 CLI 子命令展示逻辑（由 C 负责）。
- 不负责 README/conda 文档（由 A 负责）。
- 不负责集成测试主导（由 D 负责）。

## Files To Touch
- `src/app/power/network_catalog.py`（新建）
- `src/app/power/tools.py`
- `src/app/schema/tool_args.py`
- `src/app/schema/types.py`

## Interfaces/Contracts
- 新增工具接口（名称冻结）：
  - `list_builtin_networks(query?: str, max_results?: int)`
  - `get_current_network_info()`
- 增强已有接口：
  - `load_builtin_network(case_name)` 在失败时返回 `ToolResult.data.suggestions`。
- `ToolResult.data` 字段规范：
  - `network_catalog`: `[{name, category?, doc?}]`
  - `current_network`: `{name?, bus_count, line_count, load_count, sgen_count, gen_count}`
  - `suggestions`: `[str]`
- 新增参数模型（名称冻结）：
  - `ListBuiltinNetworksArgs`
  - `GetCurrentNetworkInfoArgs`

## Implementation Steps
1. 新建 `network_catalog.py`：
   - 通过 `pandapower.networks` introspection 发现可调用网络函数。
   - 过滤规则：仅保留零参数或全默认参数的可调用项。
   - 输出统一结构：`name`, `doc`（可选），`category`（可选）。
2. 在 `tool_args.py` 增加：
   - `ListBuiltinNetworksArgs(query=None, max_results=20)`，含范围校验（1~200）。
   - `GetCurrentNetworkInfoArgs` 空模型。
3. 在 `tools.py` 新增 handler：
   - `list_builtin_networks`：支持 query 模糊过滤和结果截断。
   - `get_current_network_info`：从 `working_net` 汇总元素计数。
4. 增强 `load_builtin_network`：
   - unknown case 时调用 `difflib.get_close_matches` 返回最多 5 条建议。
   - 错误消息加入引导：可用 `agent networks --query`。
5. 更新 `TOOL_SPECS`：
   - 注册新工具并确保 schema 可被 OpenAI tool calling 使用。

## Acceptance Criteria
- `list_builtin_networks` 默认返回列表且包含 `case14`。
- `query` 过滤有效，`max_results` 上限生效。
- `get_current_network_info` 在有/无网络两种状态下返回可解释信息。
- 错误 case（如 `case1x`）可返回 suggestions 且不抛未捕获异常。

## Risks & Mitigations
- 风险：introspection 误包含不应暴露的函数。
  - 缓解：白名单规则 + 单测验证输出集合。
- 风险：部分网络函数调用耗时或副作用异常。
  - 缓解：发现阶段只做函数签名检查，不实际构网；真正构网在 `load_builtin_network`。
- 风险：建议匹配结果质量不稳定。
  - 缓解：限定候选来源为发现列表，统一 `lower()` 比较并按相似度排序。

## Handoff Output
- 新增 `network_catalog.py` 与工具层改动说明。
- 更新后的工具 schema 清单（名称、参数、示例输入）。
- 失败建议机制设计说明与示例输出。
