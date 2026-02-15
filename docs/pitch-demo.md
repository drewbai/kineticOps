# KineticOps Hackathon Pitch + Demo Script

## 30-second pitch

KineticOps turns noisy ops signals into actionable intent in seconds.

Instead of manually triaging raw events, we classify each event into categories like `NetworkIssue`, `AuthFailure`, `StorageWarning`, or `ServiceFailure`, attach a confidence score, and produce a clear reason that can drive safe next steps.

The key value: **fast incident understanding with deterministic fallback**. Even when remote AI is unavailable, KineticOps still works locally with predictable behavior.

## 2–3 minute live demo script

### 1) Problem (20s)

"Ops teams waste time translating raw alerts into action. We built KineticOps to automate that first decision layer."

### 2) Architecture (25s)

"Here’s the flow: telemetry event -> rule engine -> AI planner. If remote AI is configured, we use it; if not, we fall back to local classification. Either way, we return a normalized intent with classification, reason, source, and confidence."

### 3) Run the demo (60–90s)

Use this command:

```bash
python scripts/run_demo.py --scenario all
```

Talk track while it runs:

- "Each scenario simulates a real ops signal: auth, network, service, storage."
- "The model/rules assign a category and confidence, plus a short reason."
- "This output can feed GitOps patch generation and verification in the next pipeline stage."

### 4) Show resilience (20s)

"For hackathon reliability, this system degrades gracefully. If remote AI fails, deterministic local paths still classify the event. The demo remains stable even offline."

### 5) Close (15s)

"KineticOps gives teams a practical AI control loop foundation: classify quickly, explain decisions, and hand off to automation safely."

## Backup demo command (single scenario)

```bash
python scripts/run_demo.py --scenario network
```

## Judge-friendly one-liners

- "We optimized for reliability first, intelligence second, and still got both."
- "Confidence and reason fields make model output operationally usable."
- "This is a safe bridge from alert noise to automation intent."

## If something breaks live

- If model/network is unstable: "The fallback path is intentional and part of the design."
- If output changes: focus on `classification`, `reason`, `confidence`, `source` as the stable contract.
- If time is short: run single-scenario demo and explain architecture diagram in README.
