"""Stand-ins for the LLM and the mailer."""

import threading
import time


class FakeLlm:
    """Answers with a function of the prompt. Counts calls."""

    model_fast = "fake-fast"
    model_reasoning = "fake-reasoning"

    def __init__(self, responder, delay: float = 0.0):
        self._responder = responder
        self._delay = delay
        self._lock = threading.Lock()
        self.calls = []

    def extract(self, conn, ws, *, purpose, system, prompt, images=None,
                model=None, file_id=None):
        if self._delay:
            time.sleep(self._delay)
        with self._lock:
            self.calls.append({"purpose": purpose, "prompt": prompt,
                               "file_id": file_id, "system": system})
        return self._responder(purpose, prompt)
