# Agent A 工作单：Conda 环境与 Get Started 体验

## Goal
- 交付英文优先的用户上手路径，确保新用户使用 `conda` 可快速完成首次运行。
- 提供清晰的 tool 使用教学，让中英用户都知道如何触发核心能力。

## In Scope
- 新增并维护 `environment.yml`。
- 重构 `README.md` 的 Getting Started 与 Tool Usage 部分（英文优先）。
- 更新 `.env.example` 并补充关键参数说明。
- 编写 Troubleshooting（API key、network not found、依赖安装失败）。

## Out of Scope
- 不实现工具层逻辑与 CLI 新命令（由 B/C 负责）。
- 不改动测试代码（由 D 负责）。
- 不引入 conda-lock。

## Files To Touch
- `README.md`
- `.env.example`
- `environment.yml`（新建）
- （可选）`plans/2026-02-28-conda-network-ux/99_integration_checklist.md` 中文档门禁勾选项

## Interfaces/Contracts
- 文档中命令必须与契约一致（见 `90_shared_contracts.md`）：
  - `agent chat`
  - `agent run "<instruction>"`
  - `agent networks [--query --max --format]`
  - `agent use <case_name>`
  - `agent tools [--format]`
- 环境变量说明至少覆盖：
  - `OPENAI_API_KEY`
  - `OPENAI_MODEL`
  - `DEFAULT_NETWORK`
  - `MAX_TOOL_CALLS_PER_TURN`
  - `STARTUP_SHOW_NETWORKS`
  - `STARTUP_NETWORK_PREVIEW_COUNT`

## Implementation Steps
1. 创建 `environment.yml`：
   - 指定 Python 版本（建议 `3.11`）。
   - 加入核心依赖：`openai`, `pandapower`, `pydantic`, `rich`, `tabulate`, `pandas`, `pytest`, `pytest-mock`。
2. 改写 README 的 Quick Start：
   - Conda 创建/激活环境。
   - 安装项目：`pip install -e .[dev]`。
   - 配置 `.env` 或导出环境变量。
3. 补 “First 5 minutes” 示例（中英各一条）：
   - 中文：切换网络 + 跑潮流 + 查看摘要。
   - 英文：add DG + run power flow + compare with base。
4. 新增 “Tool Learning Path”：
   - `agent tools` 如何查看工具与参数。
   - 自然语言到工具映射示例。
5. 新增 Troubleshooting：
   - `OPENAI_API_KEY` 缺失报错处理。
   - network 不存在时如何先 `agent networks --query ...`。
   - pandapower 导入失败时的 conda 解决路径。

## Acceptance Criteria
- 从空环境按 README 执行，10 分钟内可完成 `agent run` 成功。
- 文档所有命令与实际 CLI 完全一致。
- 示例覆盖至少 1 条中文、1 条英文任务。
- 常见问题覆盖 API key 缺失与 network not found 两类高频问题。

## Risks & Mitigations
- 风险：README 先写完，但 B/C 命令名变更导致失配。
  - 缓解：命令名以 `90_shared_contracts.md` 为准，最终集成前做一次全文校对。
- 风险：不同操作系统 conda 命令细节差异。
  - 缓解：主文档给通用流程，补充 OS 差异提示。
- 风险：用户直接复制命令失败。
  - 缓解：每段命令前给前置条件与期望输出样例。

## Handoff Output
- 可直接发布的 `environment.yml`。
- 英文优先且可执行的 `README.md` Get Started。
- 更新后的 `.env.example` 与参数说明。
- 文档变更清单（命令、示例、FAQ）。
