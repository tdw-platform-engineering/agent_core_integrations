import os
import json

from .modules.config import BYPASS_TOOL_CONSENT

os.environ["BYPASS_TOOL_CONSENT"] = BYPASS_TOOL_CONSENT

from strands import Agent
from bedrock_agentcore import BedrockAgentCoreApp

from .models.bedrock import load_model
from .modules.hooks import validate_request, format_response
from .prompts.system import SYSTEM_PROMPT

app = BedrockAgentCoreApp()
log = app.logger


def parse_agent_output(raw: str) -> tuple[str, bool]:
    """Extract txt and end from the LLM's JSON response."""
    try:
        data = json.loads(raw)
        return str(data.get("txt", raw)), bool(data.get("end", True))
    except (json.JSONDecodeError, AttributeError):
        return raw, True


@app.entrypoint
async def invoke(payload: dict, context):
    request = validate_request(payload)
    session_id = request.runtime_session_id
    log.info(f"Session: {session_id} | Input length: {len(request.input)}")

    agent = Agent(
        model=load_model(),
        system_prompt=SYSTEM_PROMPT,
    )

    result = agent(request.input)
    txt, end = parse_agent_output(str(result))

    response = format_response(
        session_id=session_id,
        text=txt,
        end=end,
    )

    log.info(f"Session: {session_id} | end={end}")
    return response


if __name__ == "__main__":
    app.run()
