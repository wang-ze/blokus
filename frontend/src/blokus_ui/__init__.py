"""Blokus Arena web app: a Gradio front end over the `blokus` engine.

It reads only plain data from the engine (game snapshots, records and ratings), so it can be
replaced without touching the game logic.
"""


def main() -> None:
    """Launch the web app, with API keys from a .env file in or above the working directory."""
    from dotenv import find_dotenv, load_dotenv

    from blokus.providers import configure_tracing
    from blokus_ui.app import launch

    load_dotenv(find_dotenv(usecwd=True))
    configure_tracing()
    launch()
