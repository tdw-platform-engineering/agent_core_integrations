# AgentCore App

Bedrock AgentCore agent with optional modules for MCP, multi-agent orchestration, web search, memory, knowledge base, and browser automation.

## Setup

```bash
uv venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Core install
uv pip install -r pyproject.toml

# With browser support
uv pip install -r pyproject.toml --extra browser

# Install AgentCore CLI
pip install bedrock-agentcore-starter-toolkit
```

## Run locally

```bash
cp .env.example .env
# edit .env with your AWS credentials/region and feature flags
python -m app.main
```

## Deployment

### 1. Configure the agent

```bash
# Interactive (recommended first time)
agentcore configure --entrypoint app/main.py --region us-east-1

# Non-interactive with defaults
agentcore configure \
  --entrypoint app/main.py \
  --name agentcore-app \
  --region us-east-1 \
  --non-interactive

# With memory enabled
agentcore configure \
  --entrypoint app/main.py \
  --name agentcore-app \
  --region us-east-1

# Without memory
agentcore configure \
  --entrypoint app/main.py \
  --name agentcore-app \
  --region us-east-1 \
  --disable-memory
```

### 2. Deploy to AWS

```bash
# Cloud build (default — no Docker required)
agentcore deploy

# With environment variables for feature flags
agentcore deploy \
  --env ENABLE_WEB_SEARCH=true \
  --env ENABLE_KNOWLEDGE_BASE=true \
  --env KNOWLEDGE_BASE_ID=your-kb-id

# Local build, deploy to cloud (requires Docker)
agentcore deploy --local-build

# With custom image tag for versioning
agentcore deploy --image-tag v1.0.0
```

### 3. Test the agent

```bash
# Basic invocation
agentcore invoke '{"input": "Hello, how are you?", "runtimeSessionId": "test-session-001"}'

# With session persistence
agentcore invoke '{"input": "What is AWS Lambda?", "runtimeSessionId": "my-session-123"}' \
  --session-id my-session-123

# Test locally (requires running local agent)
agentcore invoke '{"input": "test"}' --local
```

### 4. Check status

```bash
agentcore status
agentcore status --verbose
```

### 5. Destroy resources

```bash
# Preview what will be destroyed
agentcore destroy --dry-run

# Destroy with confirmation
agentcore destroy

# Force destroy without prompts
agentcore destroy --force --delete-ecr-repo
```

### Deploy with Docker (alternative)

```bash
docker build -t agentcore-app .
docker run --env-file .env -p 8000:8000 agentcore-app
```

## Memory Management

```bash
# Create memory (STM only)
agentcore memory create my_agent_memory --region us-east-1

# Create memory with long-term strategies
agentcore memory create my_agent_memory \
  --strategies '[{"semanticMemoryStrategy": {"name": "Facts"}}, {"userPreferenceMemoryStrategy": {"name": "Preferences"}}, {"summaryMemoryStrategy": {"name": "Summaries"}}]' \
  --wait

# List / check / delete
agentcore memory list
agentcore memory status <memory-id>
agentcore memory delete <memory-id> --wait
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
| `ENABLE_THINKING` | `false` | Claude extended/interleaved thinking |
| `THINKING_BUDGET` | `4096` | Max tokens for thinking budget |
| `ENABLE_ATHENA` | `false` | SQL queries via Lambda → Athena |
| `ENABLE_CART` | `false` | Persistent product list per session (DynamoDB) |

## Module Details

### MCP Server (`ENABLE_MCP=true`)

Connects to any MCP-compatible server. Configure transport via:

- `MCP_TRANSPORT=stdio` (default) — launches a subprocess
- `MCP_TRANSPORT=http` — connects to a remote Streamable-HTTP endpoint

### Multi-Agent (`ENABLE_MULTI_AGENT=true`)

Runs a three-agent pipeline: Researcher → Analyst → Writer. All enabled tools are passed to the Researcher agent automatically. Each agent can use a different model via `RESEARCHER_MODEL_ID`, `ANALYST_MODEL_ID`, `WRITER_MODEL_ID`.

### Web Search (`ENABLE_WEB_SEARCH=true`)

Adds the `http_request` tool so the agent can fetch data from any URL/API.

### Memory (`ENABLE_MEMORY=true`)

Integrates with AgentCore Memory for conversational persistence. Requires `MEMORY_ID`.

### Knowledge Base (`ENABLE_KNOWLEDGE_BASE=true`)

Uses the `retrieve` tool to query a Bedrock Knowledge Base. Requires `KNOWLEDGE_BASE_ID`.

### Browser (`ENABLE_BROWSER=true`)

Uses AgentCore Browser (managed Chrome via CDP) with two modes:

- Agent tool mode: The LLM decides when to browse via Browser-Use SDK.
- Direct Playwright mode: Programmatic control for scripted automation.

```python
from app.modules.browser_provider import run_playwright_session

def scrape(page):
    page.goto("https://www.amazon.com")
    page.fill("input#twotabsearchtextbox", "laptop")
    page.press("input#twotabsearchtextbox", "Enter")
    page.wait_for_selector("div.s-main-slot", timeout=10000)
    page.screenshot(path="search.png")

run_playwright_session(scrape)
```

### Athena SQL (`ENABLE_ATHENA=true`)

Invokes a Lambda function that executes read-only SQL queries against Athena. Requires `ATHENA_LAMBDA_NAME` (function name or full ARN) and optionally `ATHENA_LAMBDA_REGION` for cross-region invocation.

### Product List (`ENABLE_CART=true`)

Persistent product list per session stored in DynamoDB. The agent uses it to track products, build quotes, and manage budgets across the conversation.

Tools: `add_to_list`, `get_list`, `remove_from_list`, `clear_list`

#### DynamoDB Table Setup

Create the table with AWS CLI:

```bash
aws dynamodb create-table \
  --table-name agentcore_product_lists \
  --attribute-definitions \
    AttributeName=session_id,AttributeType=S \
    AttributeName=cveproduct,AttributeType=S \
  --key-schema \
    AttributeName=session_id,KeyType=HASH \
    AttributeName=cveproduct,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

Or with PowerShell:

```powershell
aws dynamodb create-table `
  --table-name agentcore_product_lists `
  --attribute-definitions `
    AttributeName=session_id,AttributeType=S `
    AttributeName=cveproduct,AttributeType=S `
  --key-schema `
    AttributeName=session_id,KeyType=HASH `
    AttributeName=cveproduct,KeyType=RANGE `
  --billing-mode PAY_PER_REQUEST `
  --region us-east-1
```

IAM permissions required for the agent's execution role:

```json
{
  "Effect": "Allow",
  "Action": [
    "dynamodb:PutItem",
    "dynamodb:UpdateItem",
    "dynamodb:DeleteItem",
    "dynamodb:Query",
    "dynamodb:BatchWriteItem",
    "dynamodb:DescribeTable",
    "dynamodb:CreateTable"
  ],
  "Resource": "arn:aws:dynamodb:us-east-1:*:table/agentcore_product_lists"
}
```

> Note: The table is also auto-created on first use if the agent's IAM role has `dynamodb:CreateTable` permission.

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
│   ├── athena_provider.py           # SQL queries via Lambda → Athena
│   └── cart_provider.py             # Persistent product list (DynamoDB)
└── prompts/
    ├── system.md                    # System prompt (main agent)
    ├── sql_rules.md                 # SQL schema, templates & rules
    ├── researcher.md                # Researcher agent prompt
    ├── analyst.md                   # Analyst agent prompt
    └── writer.md                    # Writer agent prompt
```

## Response format

```json
{
  "output": {
    "answer": "...",
    "sessionId": "...",
    "end": true
  }
}
```
