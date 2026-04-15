"""Pre/post invocation hooks for validation and response formatting."""

from pydantic import ValidationError
from ..models.schemas import AgentRequest, AgentResponse


def validate_request(payload: dict) -> AgentRequest:
    """Validate incoming payload before agent invocation."""
    try:
        return AgentRequest(**payload)
    except ValidationError as e:
        raise ValueError(f"Invalid request: {e}")


def format_response(session_id: str, text: str, end: bool) -> dict:
    """Build and validate the structured response.

    Returns the format the bedrock-agent-backend expects:
      {"output": {"answer": "...", "sessionId": "...", "end": true}}
    """
    response = AgentResponse.build(session_id=session_id, text=text, end=end)
    return response.model_dump()
