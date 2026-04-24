from pydantic import BaseModel, Field
from typing import Any


class AgentRequest(BaseModel):
    """Incoming request payload.

    Supports two input formats from the backend:
      - Flat:   {"input": "question text", "runtimeSessionId": "..."}
      - Nested: {"input": {"question": "question text"}, ...}
    """

    input: Any = Field(..., alias="input")
    session_attributes: dict = Field(default_factory=dict, alias="sessionAttributes")
    runtime_session_id: str = Field(default="", alias="runtimeSessionId")

    model_config = {"populate_by_name": True}

    @property
    def question(self) -> str:
        """Extract the user question regardless of input format."""
        if isinstance(self.input, dict):
            return str(self.input.get("question", ""))
        return str(self.input)


class AgentResponse(BaseModel):
    """Structured output returned by the agent.

    Returns a format compatible with the bedrock-agent-backend:
      {"output": {"answer": "...", "sessionId": "...", "end": true, "tokenUsage": {...}}}
    """

    output: dict

    @classmethod
    def build(cls, session_id: str, text: str, end: bool, token_usage: dict | None = None) -> "AgentResponse":
        output: dict[str, Any] = {
            "answer": text,
            "sessionId": session_id,
            "end": end,
        }
        if token_usage:
            output["tokenUsage"] = token_usage
        return cls(output=output)
