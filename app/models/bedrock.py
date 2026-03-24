from strands.models import BedrockModel
from ..modules.config import MODEL_ID


def load_model() -> BedrockModel:
    return BedrockModel(model_id=MODEL_ID)
