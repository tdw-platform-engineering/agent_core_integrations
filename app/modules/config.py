import os


BYPASS_TOOL_CONSENT = os.getenv("BYPASS_TOOL_CONSENT", "true")
MODEL_ID = os.getenv("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
