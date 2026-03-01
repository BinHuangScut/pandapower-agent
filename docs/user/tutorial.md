# pandapower-agent 教程（能力全景版）

本教程面向第一次使用本项目的用户，目标是用最短路径把核心能力都跑一遍，包括：
- 内置电网检索与切换
- AC/DC/三相潮流
- 短路、拓扑、N-1、诊断
- 电网编辑（增删改、投退）
- 场景保存/加载/对比/回滚
- OPF 与状态估计
- 结果导出与调试模式

## 1. 环境准备

```bash
conda env create -f environment.yml
conda activate pandapower-agent
pip install -e .[dev]
```
项目内配置（不需要写 `~/.bashrc` / `~/.zshrc`）：

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_api_key
OPENAI_MODEL=gpt-4.1-mini
DEFAULT_NETWORK=case14
MAX_TOOL_CALLS_PER_TURN=6
```

Google AI Studio（Gemini）可选配置：

```env
LLM_PROVIDER=google
GOOGLE_API_KEY=your_google_api_key
GOOGLE_MODEL=gemini-2.5-flash
GOOGLE_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
DEFAULT_NETWORK=case14
MAX_TOOL_CALLS_PER_TURN=6
```

CLI 会自动加载项目根目录 `.env`；如果 `.env` 缺失，会回退读取 `.env.example`。

说明：
- `agent run` 和 `agent chat` 需要当前 provider 对应的 key（`OPENAI_API_KEY` 或 `GOOGLE_API_KEY`）。
- `agent networks/use/tools/scenarios/undo/export/plot/plot-network` 可独立使用，不依赖 LLM。

## 2. 3 分钟热身

```bash
agent networks --query case --max 10
agent use case14
agent tools
agent run "运行交流潮流并总结电压风险和线路越限风险"
```

你会看到：
- 网络列表与当前网络信息表格
- 工具目录（含中英文示例）
- `assistant>` 风格的自然语言总结

## 3. `run` 与 `chat` 的区别（很重要）

- `agent run "<指令>"`：单次任务，适合“一句话完成一个分析流程”。
- `agent chat`：多轮会话，适合逐步编辑网络、保存场景、对比与回滚。

如果你要做连续实验（改参数 -> 重算 -> 对比 -> 导出），优先用 `chat`。

## 4. 一次性展示多能力（`agent run`）

下面是一条可直接复制的综合任务，通常会触发多个工具联动：

```bash
agent run "在默认网络上先做交流潮流，再做拓扑分析，再对线路做N-1筛查返回前5个最严重故障，最后给出运行建议"
```

再试一个“故障 + 指定母线”任务：

```bash
agent run "执行最大三相短路分析，只关注母线[1,5,10]，并按短路电流从高到低总结结论"
```

## 5. 状态化实战（推荐：`agent chat`）

启动：

```bash
agent chat
```

在会话里按顺序输入以下内容：

```text
/use case14
运行交流潮流并总结关键风险
在3号母线新增5MW负荷，重跑潮流，并把当前状态保存为 load_up
在3号母线新增2MW静态电源，重跑潮流，并把当前状态保存为 dg_support
对比场景 load_up 和 dg_support，关注 max_line_loading_pct,min_bus_vm_pu,total_active_loss_mw
/scenarios
/undo
/export summary ./outputs/summary.json
/export results ./outputs/results.json
exit
```

这段流程覆盖了：
- 元件创建（`create_load` / `create_sgen`）
- 分析重算（`run_power_flow`）
- 场景管理（`save_scenario` / `compare_scenarios` / `list_scenarios`）
- 回滚（`undo_last_mutation`）
- 导出（summary/results）

## 6. 能力清单与即用提示词

复制下面任一条到 `agent run "<这里>"` 或 `chat` 对话中：

```text
运行直流潮流，并对比它和交流潮流的关键指标差异
运行三相潮流，并总结最需要关注的电压问题
执行网络诊断，给出最值得优先修复的建模问题
运行拓扑分析，告诉我是否有孤岛和失供母线
对线路和变压器进行N-1筛查，返回前10个最严重故障
把所有负荷有功统一增加10%，重跑潮流并总结变化
将line 3退出运行后重跑潮流，并评估风险
把line 0的max_i_ka调整为0.4，再跑潮流看是否出现过载
创建一条from_bus=1,to_bus=4的新线路并重跑潮流
运行OPF并总结目标函数与收敛情况
运行状态估计（synthetic measurement），给出是否收敛
```

## 7. Chat 内置快捷命令

在 `agent chat` 中可直接使用：

```text
/networks
/use <case_name>
/tools
/scenarios
/undo
/plot ./outputs/analysis_plot.png run_short_circuit ikss_ka bar
/plotnet ./outputs/network_plot.png
/export <summary|results> <path>
/reset
/exit
```

## 8. 调试模式（查看工具调用轨迹）

如果你想确认每一步具体调用了什么工具：

```bash
agent run "运行交流潮流并总结风险" --admin-key 525400
```

或：

```bash
agent chat --admin-key 525400
```

会显示 `Debug Tool Traces` 表格（工具名、参数、是否成功、消息）。

聊天中也可动态开关：

```text
/admin unlock 525400
/admin off
```

## 9. 结果导出与自动缓存

- 会话内导出：
  - `/export summary ./outputs/summary.json`
  - `/export results ./outputs/results.json`
- 可视化导出（PNG）：
  - `/plot ./outputs/analysis_plot.png`
  - `/plot ./outputs/sc_ikss.png run_short_circuit ikss_ka bar`
  - `/plotnet ./outputs/network_plot.png`
- 命令行导出：
  - `agent export --type summary --path ./outputs/summary.json`
  - `agent export --type results --path ./outputs/results.json`
  - `agent plot --path ./outputs/analysis_plot.png --tool run_power_flow`
  - `agent plot-network --path ./outputs/network_plot.png --library networkx`
  - `plot-network` 默认显示母线编号（节点标号）；可用 `--hide-bus-labels` 关闭，`--label-font-size` 调整字号。
  - 若当前没有活动网络，`agent plot-network` 会先自动加载 `DEFAULT_NETWORK` 再绘图。

如果当前进程没有结果，程序会尝试读取 `.agent_last_results.json` 缓存。

## 10. 常见报错与处理

- `RuntimeError: OPENAI_API_KEY is required`
  - 说明：`OPENAI_API_KEY` 未正确配置。
  - 处理：在项目根目录 `.env` 或 `.env.example` 中配置该值。

- `RuntimeError: GOOGLE_API_KEY is required for LLM_PROVIDER=google`
  - 说明：Google provider 下 key 未正确配置。
  - 处理：在 `.env` 配置 `GOOGLE_API_KEY`，或用 `OPENAI_API_KEY` 作为兼容回退。

- `Unknown built-in network: xxx`
  - 说明：网络名不存在或拼写不准确。
  - 处理：先 `agent networks --query <keyword>` 再精确选择。

- `No results available to export in current session.`
  - 说明：还没产出可导出的分析结果。
  - 处理：先跑一次分析，再导出。

- `[Notice] Reached max tool calls in this turn (...)`
  - 说明：单轮工具调用达到上限（默认 6）。
  - 处理：拆分任务到多轮，或在 `.env` 提高 `MAX_TOOL_CALLS_PER_TURN`。

- `Seaborn plotting dependencies are not installed.`
  - 说明：当前环境缺少绘图依赖。
  - 处理：在激活的环境里执行 `pip install -e .[dev]`，无需单独安装某个包。

---

你可以把本教程当作“回归脚本”：每次升级模型、工具或依赖后，完整跑一遍第 5 节，基本就能覆盖主要能力是否正常。
