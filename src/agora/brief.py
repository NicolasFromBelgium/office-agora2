"""CLI: dump project state for Grok (the agent) to read.

    python -m agora.brief
"""

from __future__ import annotations

from agora.db import make_engine, make_session_factory, run_migrations
from agora.services.snapshot import capture_state, render_markdown, write_state_file
from agora.settings import load_settings


def main() -> None:
    settings = load_settings()
    run_migrations(settings.database_url)
    engine = make_engine(settings.database_url)
    factory = make_session_factory(engine)
    try:
        with factory() as session:
            state = capture_state(session)
            path = write_state_file(session, settings)
    finally:
        engine.dispose()
    text = render_markdown(state)
    print(text, end="")
    print(f"\n# écrit aussi dans {path}", end="\n")


if __name__ == "__main__":
    main()
