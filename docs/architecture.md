# ShopAssist AI — Architecture

## System Overview

ShopAssist is a full-stack AI customer-support agent for a mock electronics store. It uses tool-calling (function calling) to interact with backend services, enforces a strict refund policy in code, and includes a comprehensive evaluation harness.

```mermaid
flowchart TD
    User["👤 Customer (Browser)"]
    FE["🖥️ Frontend\nReact + Vite\n(standalone.html)"]
    API["⚙️ FastAPI Backend\nPOST /chat\nPOST /chat/confirm\nGET /sessions/:id\nGET /traces\nGET /health"]
    Agent["🤖 Agent Loop\nagent.py"]
    Guard["🛡️ Guardrails\nguardrails.py\n• Injection detection\n• Hallucination guard\n• Confirmation gate\n• Identity check\n• Escalation rules"]
    LLM["🧠 LLM Provider\n(Gemini / Ollama / Mock)"]
    Tools["🔧 Tool Registry\nregistry.py\n• get_order_status\n• check_refund_eligibility\n• create_refund_request\n• create_support_ticket\n• search_policy\n• escalate_to_human"]
    DB["🗄️ SQLite + SQLAlchemy\nshopassist.db\n• customers / products\n• orders / order_items\n• refund_requests / tickets\n• escalations / traces\n• pending_actions"]
    Eval["📊 Eval Harness\nrun_eval.py\ncompare.py\n64 YAML scenarios"]

    User -->|HTTP| FE
    FE -->|POST /chat| API
    API --> Agent
    Agent --> Guard
    Guard -->|flagged / blocked| Agent
    Agent -->|prompt + tools| LLM
    LLM -->|tool_call| Agent
    Agent -->|validate args\nPydantic| Tools
    Tools -->|read / write| DB
    Tools -->|result| Agent
    Agent -->|log turn| DB
    Agent -->|reply + pending_action| API
    API -->|JSON response| FE
    FE -->|POST /chat/confirm| API
    Eval -.->|drives agent turns| Agent
    Eval -.->|reads results| DB
```

## Component Descriptions

### Frontend (`shopassist/frontend/`)
- **React + Vite** SPA (also available as `standalone.html` — no build step required)
- **Chat page**: Message bubbles, tool-call cards (collapsible), Confirm/Cancel buttons for write actions, escalation banner, New Session button
- **Trace viewer**: Per-session timeline of LLM calls, tool calls, latencies, tokens, guardrail events

### FastAPI Backend (`shopassist/backend/app/`)
- **`main.py`**: 7 endpoints with lifespan context, CORS, OpenAPI docs at `/docs`
- **`config.py`**: All settings read from `.env` via `pydantic-settings`; zero hardcoded secrets

### Agent Loop (`app/agent/agent.py`)
1. Load session history from DB
2. Run guardrails on user input (injection, abusive language)
3. Call LLM with system prompt + history + tool schemas
4. If LLM requests a tool → validate args (Pydantic) → check if WRITE tool → gate behind confirmation
5. Execute tool → append result → loop (max 6 tool steps)
6. Run output guardrails (hallucination check)
7. Log everything to `traces` table

### Guardrails (`app/agent/guardrails.py`)
All guards are toggled with `GUARDRAILS_ENABLED` env flag for before/after comparison.

| Guard | Mechanism | Failure Mode Caught |
|-------|-----------|-------------------|
| Injection detection | Regex patterns (`ignore previous`, `you are now`, `act as admin`) | Prompt injection attacks |
| Identity check | Email↔order match in tool code | Cross-customer data access |
| Policy enforcement | Code-level checks in `implementations.py` | LLM refund override attempts |
| Confirmation gate | `pending_action` token, 10-min TTL | Accidental write operations |
| Hallucination guard | Cross-check reply against tool results | Fabricated order IDs/amounts |
| Anger/abuse detector | Keyword + intensity heuristics | Abusive customers needing escalation |
| Out-of-scope detector | Topic heuristics + prompt instructions | Homework / competitor questions |

### LLM Providers (`app/agent/llm/`)

```mermaid
classDiagram
    class LLMProvider {
        <<abstract>>
        +chat(messages, tools) LLMResponse
    }
    class GeminiProvider {
        +model: str
        +client: genai.Client
        +chat()
    }
    class OllamaProvider {
        +base_url: str
        +model: str
        +chat()
    }
    class MockProvider {
        +scripts: dict
        +chat()
    }
    LLMProvider <|-- GeminiProvider
    LLMProvider <|-- OllamaProvider
    LLMProvider <|-- MockProvider
```

### Data Model

```mermaid
erDiagram
    CUSTOMERS ||--o{ ORDERS : places
    ORDERS ||--o{ ORDER_ITEMS : contains
    ORDER_ITEMS }o--|| PRODUCTS : references
    ORDERS ||--o{ REFUND_REQUESTS : has
    CUSTOMERS ||--o{ TICKETS : files
    TRACES {
        string session_id
        int turn
        string role
        string content
        string tool_name
        json tool_args
        json tool_result
        int latency_ms
        int input_tokens
        int output_tokens
        string error
    }
    PENDING_ACTIONS {
        string action_id
        string session_id
        string tool_name
        json tool_args
        datetime expires_at
        bool confirmed
    }
```

### Evaluation Harness (`shopassist/backend/eval/`)

```mermaid
flowchart LR
    YAML["📄 64 YAML Scenarios\n10 categories"]
    Runner["run_eval.py\n• Load scenarios\n• Reset DB\n• Run agent\n• Score metrics"]
    JSON["results.json"]
    MD["summary.md"]
    Compare["compare.py\n• Baseline vs Guarded\n• Delta table\n• Fixed / Regressed"]
    Report["comparison.md"]

    YAML --> Runner
    Runner --> JSON
    Runner --> MD
    JSON --> Compare
    Compare --> Report
```

**9 Metrics measured:**
1. Task Success Rate
2. Tool Selection Accuracy
3. Tool Argument Validity Rate
4. Policy Violation Rate
5. Prompt-Injection Resistance
6. Hallucination Rate
7. Unnecessary Escalation Rate
8. Consistency Across Repeats
9. Average Latency per Turn

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Policy enforced in code, not only prompt** | LLMs can be manipulated; code cannot be overridden by a prompt injection |
| **MockProvider for tests** | Tests run in milliseconds, never call a real API, are 100% deterministic |
| **SQLite + SQLAlchemy 2.0** | Zero-config persistence; swappable to PostgreSQL by changing `DATABASE_URL` |
| **Pydantic v2 for tool args** | Strict validation with regex, enums, and email format before any DB write |
| **Confirmation gate for WRITE tools** | Prevents accidental or injected data mutations; user must explicitly confirm |
| **Hallucination guard** | Checks every outbound reply against tool results seen in that session |
| **`standalone.html`** | Full-featured frontend that works without Node.js — open in browser while backend runs |
| **Fixed random seed (42)** | Reproducible seed data; deterministic order eligibility windows for eval |
