"""Backward-compatible command-line entry point for Chronicle Research Agent."""

from research_agents import *  # noqa: F401,F403
from research_agents.cli import main

if __name__ == "__main__":
    main()
