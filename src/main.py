"""Thin entrypoint that re-exports the app from the app package."""
from app.main import app  # noqa: F401

if __name__ == "__main__":
    app.run()
