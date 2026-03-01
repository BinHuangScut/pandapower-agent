# Architecture

```mermaid
flowchart LR
    U[User CLI Command] --> C[CLI Layer\nargparse + chat shell]
    C --> A[Agent Runtime\nOpenAI/Gemini tool calling]
    A --> T[Tool Executor\nvalidated tool schemas]
    T --> S[Session State\nnetwork + snapshots + undo]
    T --> P[pandapower Engine\nAC/DC/3ph/SC/OPF/SE]
    P --> R[Structured Results\nmachine_summary + tables]
    R --> O[Render and Export\nterminal/json/png]
```

## Runtime principles

- LLM orchestrates, pandapower computes truth.
- Every mutating operation is snapshot-aware for undo/recovery.
- Tools enforce schema-validated args before execution.
- Results are both human-readable and machine-structured.
