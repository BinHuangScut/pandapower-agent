# 从自然语言到电网仿真：`pandapower-agent` 技术构建全解

如果把这个项目一句话说清楚，它是一个“会调用电力分析工具的 CLI 智能体”：

- 你输入自然语言（中文或英文）
- Agent 把需求拆成结构化工具调用
- 后端用 `pandapower` 跑计算
- 最后返回可读结论和可导出的结构化结果

这篇文档聚焦两件事：**用了哪些技术**、**它是怎么一步步被构建出来的**。

## 1. 目标与设计边界

项目目标不是做一个“会聊天的 bot”，而是做一个“可执行、可追溯、可回滚”的电力分析工作台。  
所以代码里有几个非常明确的边界：

- 数值结果尽量来自工具，不靠模型“猜”
- 工具调用必须是白名单，参数必须校验
- 对网络有改动的操作支持回滚（`undo`）
- 结果要能导出（`summary/results`），并有缓存兜底

这些边界直接决定了架构。

## 2. 技术栈选型

核心技术非常克制，几乎都在做“稳定工程能力”：

- **Python + argparse**：CLI 框架（`agent run/chat/networks/use/...`）
- **OpenAI SDK tool calling**：`openai` provider 走 Responses API，`google` provider 走 OpenAI-compatible Chat Completions
- **pandapower**：电网建模与仿真内核（潮流、短路、拓扑、N-1、OPF、状态估计）
- **Pydantic v2**：工具参数 schema 与运行时校验
- **Rich**：终端表格和可读输出
- **Pytest + monkeypatch**：以单测方式验证调度与工具行为

`pyproject.toml` 里的依赖非常清晰，说明这不是“框架堆砌型”工程，而是以功能闭环为优先的最小技术集合。

## 3. 分层架构：从 CLI 到仿真引擎

项目可以拆成 4 层：

1. **交互层（CLI）**  
   `src/app/main.py` 负责命令解析、chat 循环、隐藏管理命令（admin debug）。

2. **智能体调度层（AgentRuntime）**  
   `src/app/agent/loop.py` 按 provider 选择调用路径（OpenAI Responses / Google Chat Completions），循环处理模型返回的 tool call，直到没有工具调用或达到上限。

3. **工具执行层（ToolExecutor）**  
   `src/app/power/tools.py` 是关键中枢：白名单分发、参数校验、异常处理、变更回滚、结果落盘。

4. **分析适配层（Analysis Modules）**  
   `src/app/power/analysis_*.py` 封装 `pandapower` 的能力，并统一产出 `machine_summary` 等结构化字段。

可以把它理解为：

```text
User -> CLI(main.py)
     -> AgentRuntime(loop.py)
     -> ToolExecutor(tools.py)
     -> pandapower(analysis modules)
     -> ToolResult + tables + machine_summary
     -> LLM final answer
```

## 4. Tool Calling 的“合同化”实现

这个项目最关键的工程决策是：**把每个能力都做成有 schema 的工具合同**。

### 4.1 工具声明

`ToolSpec`（`tools.py`）定义了工具最小合同：

- `name/description`
- `args_model`（Pydantic 模型）
- `handler`（执行函数）
- `mutating`（是否会修改网络）

然后统一转换成两类 schema（`to_responses_tool()` / `to_chat_tool()`）。

### 4.2 参数校验

每个工具参数在 `src/app/schema/tool_args.py` 里建模，例如：

- `RunContingencyScreeningArgs`：限定 `element_types/top_k/max_outages` 等范围
- `SetLoadArgs`：要求 `p_mw_delta` 与 `q_mvar_delta` 至少给一个
- `SaveScenarioArgs`：禁止使用保留名称 `current`

好处是“错误尽量前置”：模型就算生成了不合理参数，也会在执行前被拦住。

### 4.3 执行与容错

`ToolExecutor.execute()` 的流程是：

1. 校验工具是否在白名单
2. 解析 JSON 参数并做 Pydantic 验证
3. 若为 `mutating` 工具，先做快照
4. 调用 handler
5. 失败自动回滚并返回结构化错误
6. 记录 `history` 与 `last_results`

这让“自然语言驱动”变成“可控执行系统”。

## 5. 状态管理：为什么能做场景对比和撤销

`SessionState`（`src/app/power/state.py`）维护了会话级状态：

- `working_net`：当前工作网络
- `scenarios`：命名场景快照（`base/current/...`）
- `mutation_log`：可回滚快照栈
- `last_results`：最近工具结果（支持导出）

关键机制有两个：

- **场景快照**：`save_scenario/load_scenario/compare_scenarios`
- **事务式回滚**：改动前 `push_mutation_snapshot`，出错后 `undo_last_mutation`

因此它天然适合“调参数 -> 重算 -> 对比 -> 回退”的工程流程。

## 6. 分析能力是怎样接进来的

分析模块几乎都是“薄适配层”，把 pandapower 能力包装成统一结果：

- `analysis_pf.py`：`runpp / rundcpp / runpp_3ph`
- `analysis_sc.py`：`shortcircuit.calc_sc`
- `analysis_topology.py`：`topology.create_nxgraph + unsupplied_buses`
- `analysis_contingency.py`：逐元件摘除，重跑潮流，计算 severity 排名
- `analysis_diagnostic.py`：`diagnostic.diagnostic`

统一返回结构里包含 `machine_summary`，这对两件事很重要：

- 给 LLM 一组稳定、可比较的核心指标
- 直接支持 `summary` 导出和场景差异比较

## 7. CLI 与可观测性设计

这个项目虽然是 CLI，但可运维性考虑得比较完整：

- `agent tools`：直接展示工具目录和示例
- `agent export` / `/export`：导出 `summary/results` JSON
- `.agent_last_results.json`：进程外缓存兜底
- admin 模式：可显示 `Debug Tool Traces`（工具名、参数、结果）

这部分让它不仅“能跑”，还“能排查问题”。

## 8. 它是怎么被构建出来的（从代码结构反推）

从当前代码形态看，这个项目采用了典型的“**先工具化，再智能化**”路线：

1. 先把电网能力拆成独立工具（每个工具可单独调用）
2. 再加会话状态（场景、回滚、结果缓存）
3. 再接 LLM tool calling（OpenAI + Google 兼容）形成自然语言调度
4. 最后补 CLI 体验（chat 命令、导出、admin trace）和测试矩阵

这种顺序的优点是：即使没有 LLM，系统也能以命令方式工作；LLM 只是“调度器”，不是“业务真相来源”。

## 9. 测试策略：保障哪些风险

测试主要覆盖三类风险：

- **调度风险**：`AgentRuntime` 工具循环、admin trace 开关
- **契约风险**：Pydantic 参数校验、保留字段限制
- **状态风险**：场景保存/加载/删除、mutation undo、CLI 命令分发

大量测试用 `monkeypatch` 替换底层依赖，快速验证控制流与失败路径，这对 Agent 类项目很实用。

## 10. 如果你要扩展一个新工具

以“新增一个分析工具”为例，最小步骤是：

1. 在 `src/app/schema/tool_args.py` 新增参数模型
2. 在 `src/app/power/analysis_*.py` 或 `tools.py` 写 handler
3. 在 `TOOL_SPECS` 注册工具（含中英文示例）
4. 为新工具补单测（成功路径 + 失败路径）
5. 在 `tutorial.md` 增加使用示例

这条路径的好处是：新增功能不会破坏现有调度结构。

---

## 总结

`pandapower-agent` 的核心价值，不是“把 LLM 接到了电力系统”，而是把它做成了一个有工程边界的执行系统：

- 上层：自然语言交互
- 中层：可验证、可回滚的工具合同
- 下层：可信的 pandapower 数值内核

所以它既能当演示型 Agent，也能作为电网分析自动化的基础骨架继续演进。
