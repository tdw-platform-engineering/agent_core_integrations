# AgentCore App

Minimal Bedrock AgentCore agent with Pydantic validation hooks.

## Setup

```bash
uv venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

uv pip install -r pyproject.toml
```

## Run locally

```bash
cp .env.example .env
# edit .env with your AWS credentials/region
python -m app.main
```

## Docker

```bash
docker build -t agentcore-app .
docker run --env-file .env -p 8000:8000 agentcore-app
```

## Structure

```
app/
├── main.py      # AgentCore entrypoint
├── schemas.py   # Pydantic request/response models
├── hooks.py     # Pre/post invocation validation hooks
└── model.py     # Bedrock model loader
```

## Response format

Every invocation returns:

```json
{
  "sessionid": "...",
  "txt": "...",
  "end": true
}
```
