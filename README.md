# AgentCore App

Bedrock AgentCore agent with optional modules for MCP, multi-agent orchestration, web search, memory, knowledge base, browser automation, and code interpreter.

## Setup

```bash
uv venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Core install
uv pip install -r pyproject.toml

# With browser support
uv pip install -r pyproject.toml --extra browser

# Everything
uv pip install -r pyproject.toml --extra all
```

## Run locally

```bash
cp .env.example .env
# edit .env with your AWS credentials/region and feature flags
python -m app.main
```

## Feature Flags

All modules are opt-in via environment variables:

| Variable | Default | Description |
|---|---|---|
| `ENABLE_MCP` | `false` | Connect to MCP servers (stdio or HTTP) |
| `ENABLE_MULTI_AGENT` | `false` | Three-agent research workflow (Researcher → Analyst → Writer) |
| `ENABLE_WEB_SEARCH` | `false` | `http_request` tool for web access |
| `ENABLE_MEMORY` | `false` | AgentCore Memory (short + long-term) |
| `ENABLE_KNOWLEDGE_BASE` | `false` | Bedrock Knowledge Base retrieval (RAG) |
| `ENABLE_BROWSER` | `false` | AgentCore Browser automation (Playwright + Browser-Use) |
| `ENABLE_CODE_INTERPRETER` | `false` | AgentCore Code Interpreter (sandboxed Python execution) |

## Module Details

### MCP Server (`ENABLE_MCP=true`)

Connects to any MCP-compatible server. Configure transport via:

- `MCP_TRANSPORT=stdio` (default) — launches a subprocess
- `MCP_TRANSPORT=http` — connects to a remote Streamable-HTTP endpoint

### Multi-Agent (`ENABLE_MULTI_AGENT=true`)

Runs a three-agent pipeline: Researcher → Analyst → Writer. All enabled tools are passed to the Researcher agent automatically.

### Web Search (`ENABLE_WEB_SEARCH=true`)

Adds the `http_request` tool so the agent can fetch data from any URL/API.

### Memory (`ENABLE_MEMORY=true`)

Integrates with AgentCore Memory for conversational persistence. Requires `MEMORY_ID`.

### Knowledge Base (`ENABLE_KNOWLEDGE_BASE=true`)

Uses the `retrieve` tool to query a Bedrock Knowledge Base. Requires `KNOWLEDGE_BASE_ID`.

### Browser (`ENABLE_BROWSER=true`)

Uses AgentCore Browser (managed Chrome via CDP) with two modes:

- **Agent tool mode**: The LLM decides when to browse. Uses Browser-Use SDK for natural-language → browser actions.
- **Direct Playwright mode**: Programmatic control for scripted automation.

```python
# Direct Playwright example
from app.modules.browser_provider import run_playwright_session

def scrape(page):
    page.goto("https://www.amazon.com")
    page.fill("input#twotabsearchtextbox", "laptop")
    page.press("input#twotabsearchtextbox", "Enter")
    page.wait_for_selector("div.s-main-slot", timeout=10000)
    page.screenshot(path="search.png")

run_playwright_session(scrape)
```

### Code Interpreter (`ENABLE_CODE_INTERPRETER=true`)

Gives the agent a sandboxed Python environment to execute code, run calculations, and analyze data via AgentCore Code Interpreter.

## Docker

```bash
docker build -t agentcore-app .
docker run --env-file .env -p 8000:8000 agentcore-app
```

## Structure

```
app/
├── main.py                          # AgentCore entrypoint + module assembly
├── models/
│   ├── bedrock.py                   # Bedrock model loader
│   └── schemas.py                   # Pydantic request/response models
├── modules/
│   ├── config.py                    # Env vars + feature flags
│   ├── hooks.py                     # Pre/post invocation validation
│   ├── mcp_provider.py              # MCP client builder
│   ├── memory_provider.py           # AgentCore Memory session manager
│   ├── knowledge_base_provider.py   # Bedrock KB retrieve tool
│   ├── multi_agent.py               # Multi-agent orchestration
│   ├── web_search_provider.py       # http_request tool
│   ├── browser_provider.py          # AgentCore Browser + Playwright
│   └── code_interpreter_provider.py # AgentCore Code Interpreter
└── prompts/
    └── system.py                    # System prompt
```

## Response format

```json
{
  "sessionid": "...",
  "txt": "...",
  "end": true
}
```
