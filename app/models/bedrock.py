"""Bedrock model loader — supports per-agent model overrides."""

from strands.models import BedrockModel
from ..modules.config import MODEL_ID


def load_model(model_id: str | None = None) -> BedrockModel:
    """Return a BedrockModel.

    Args:
        model_id: Optional override. If empty/None, falls back to MODEL_ID.
    """
    return BedrockModel(model_id=model_id or MODEL_ID)
