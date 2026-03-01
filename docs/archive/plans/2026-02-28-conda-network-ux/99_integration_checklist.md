# 集成检查清单（Pre / Post / Release Gates）

## Goal
- 提供统一的集成执行清单，确保多 Agent 产物可以顺利合并并达到上线门槛。

## In Scope
- 集成前一致性检查（接口、命令、文档）。
- 集成后功能验收（冷启动、中英任务、错误恢复）。
- 发布门禁（测试通过、文档可执行、无破坏性变更）。

## Out of Scope
- 不替代详细测试设计（见 Agent D 工作单）。
- 不定义功能需求本身（见主计划与契约文档）。

## Files To Touch
- 本文件（`plans/2026-02-28-conda-network-ux/99_integration_checklist.md`）
- 集成阶段可能补充的问题记录文件（可选）

## Interfaces/Contracts
- 核对来源：
  - 主计划：`00_master_plan.md`
  - 共享契约：`90_shared_contracts.md`
  - Agent 分工：`01~04_agent_*.md`
- 验收命令与工具必须与契约完全一致。

## Implementation Steps
1. 集成前检查（Pre-Integration）
   - [ ] `90_shared_contracts.md` 与实现接口逐条一致。
   - [ ] CLI 帮助信息包含 `networks/use/tools` 且参数一致。
   - [ ] README 命令与实际可执行命令一致。
   - [ ] `.env.example` 包含新增配置项。
2. 集成后验收（Post-Integration）
   - [ ] 冷启动流程：Conda -> 安装 -> 配置 -> 首次 `agent run` 成功。
   - [ ] `agent networks` 默认含 `case14`。
   - [ ] `agent networks --query 118` 返回过滤结果。
   - [ ] `agent use case14` 成功并回显网络摘要。
   - [ ] `agent use wrong_name` 失败并返回 suggestions。
   - [ ] chat 首屏主动展示网络预览（可配置关闭）。
   - [ ] 自然语言“有哪些内置系统”触发 `list_builtin_networks`。
   - [ ] 中英各一条任务可端到端完成。
3. 发布门禁（Release Gates）
   - [ ] 自动化测试全部通过（新增 + 回归）。
   - [ ] 无未捕获异常导致 CLI 崩溃。
   - [ ] README 所有命令可复制执行。
   - [ ] 无破坏性接口变更（或有明确版本说明）。

## Acceptance Criteria
- 上述清单项全部勾选通过。
- 任一失败项都有缺陷单、复现步骤和责任归属。
- 最终交付可复现、可运行、可教学。

## Risks & Mitigations
- 风险：集成顺序错误导致问题定位困难。
  - 缓解：严格按 Pre -> Post -> Release Gate 顺序执行。
- 风险：不同 Agent 交付时间不一致。
  - 缓解：先进行契约一致性检查，再进行功能联调。
- 风险：仅跑单测未覆盖真实使用路径。
  - 缓解：门禁强制包含冷启动和中英任务的端到端验证。

## Handoff Output
- 集成执行记录（勾选版）。
- 问题清单与修复状态。
- 最终验收结论（Go / No-Go）。
