from pydantic import BaseModel, Field


class AgentRequest(BaseModel):
    """Incoming request payload."""

    input: str = Field(..., alias="input", min_length=1, max_length=10000)
    session_attributes: dict = Field(default_factory=dict, alias="sessionAttributes")
    runtime_session_id: str = Field(..., alias="runtimeSessionId", min_length=1)

    model_config = {"populate_by_name": True}



class AgentResponse(BaseModel):
    """Structured output returned by the agent."""

    sessionid: str
    txt: str
    end: bool
