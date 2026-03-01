# pandapower-agent

Natural-language power-system analysis on top of `pandapower`: ask in plain English (or Chinese), run trusted calculations, and export reproducible results.

![Quick Demo (30s)](docs/assets/quick-demo.gif)

## Why this project

`pandapower-agent` bridges LLM interaction and deterministic grid simulation so teams can go from question to validated analysis quickly.

## Technical approach (high level)

`pandapower-agent` follows a layered path from natural-language intent to deterministic simulation output:

1. **Intent intake (CLI)**: `agent run` / `agent chat` receives a natural-language task.
2. **LLM orchestration**: OpenAI/Gemini tool-calling plans which analysis tools to invoke.
3. **Validated tool execution**: tool schemas validate arguments before handlers run.
4. **Stateful simulation context**: network state + snapshots support scenario edits and undo.
5. **Deterministic compute core**: `pandapower` executes AC/DC/3-phase flow, short-circuit, OPF, etc.
6. **Structured delivery**: results are rendered for terminal reading and exported as JSON/plots.

See also: [Architecture](docs/architecture.md) and [Technical intro (public)](technical-intro-public.md).

## High-value scenarios

- **Operations risk scan**: run AC/DC/3-phase power flow and summarize voltage/loading risks.
- **Reliability screening**: run topology + N-1 contingency + short-circuit checks in one workflow.
- **Planning iterations**: edit network elements, save/compare scenarios, and undo safely.

## 60-second quickstart (PyPI)

```bash
python -m venv .venv
source .venv/bin/activate
pip install pandapower-agent
agent networks --max 8
agent use case14
agent doctor --format table
```

## Full setup (Conda + dev)

```bash
conda env create -f environment.yml
conda activate pandapower-agent
pip install -e .[dev]
```

## No-key experience

These commands work without any API key:

```bash
agent networks
agent use case14
agent tools
agent doctor
agent plot-network --path ./outputs/network_plot.png
```

## With API key (agent run/chat)

Interactive setup wizard:

```bash
agent config init
```

Create `.env` in project root:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_api_key
OPENAI_MODEL=gpt-4.1-mini
DEFAULT_NETWORK=case14
MAX_TOOL_CALLS_PER_TURN=6
```

Then run:

```bash
agent run "run AC power flow and summarize voltage and loading risks"
```

Gemini (AI Studio) is also supported:

```env
LLM_PROVIDER=google
GOOGLE_API_KEY=your_google_api_key
GOOGLE_MODEL=gemini-2.5-flash
GOOGLE_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
```

## Recommended minimal command set

- `agent networks`
- `agent use <case_name>`
- `agent tools`
- `agent config init`
- `agent run "<instruction>"`
- `agent chat`
- `agent doctor`
- `agent export --type summary|results --path <file.json>`
- `agent plot --path <file.png>`

## Demo script

```bash
scripts/demo_flow.sh
```

## Documentation

- Architecture: [docs/architecture.md](docs/architecture.md)
- Chinese docs entry: [docs/zh/README.zh-CN.md](docs/zh/README.zh-CN.md)
- Tutorial: [tutorial.md](tutorial.md)
- Technical intro (public): [technical-intro-public.md](technical-intro-public.md)

## Contributing and community

- Contributing guide: [CONTRIBUTING.md](CONTRIBUTING.md)
- Code of Conduct: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- Security policy: [SECURITY.md](SECURITY.md)
- Changelog: [CHANGELOG.md](CHANGELOG.md)

## License

MIT, see [LICENSE](LICENSE).

---

If this project helps you, please **Star + Try + Share a case**.
