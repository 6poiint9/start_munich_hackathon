"""Reads documents, scans and mails into facts with the LLM (wave 2)."""

from typing import Any

from lineguard import runtime
from lineguard.agents.reader import kinds


def read(rt: runtime.Runtime, route: Any, file: dict[str, Any], ctx: kinds.Context) -> bool:
    """Reads one document.

    Returns:
        False when no LLM is configured. The file then keeps its status and
        is read later.
    """
    del route, file, ctx
    if rt.llm is None:
        return False
    raise NotImplementedError("The document reader is built in step A6")
