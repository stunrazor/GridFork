"""Guard: the suite is offline — no test may touch the real network.

Every test that needs HTTP rigs ``httpx.get``/``httpx.post`` itself; this
autouse fixture makes any unrigged call fail loudly instead of slow,
flaky, or secretly live.
"""

import httpx
import pytest


@pytest.fixture(autouse=True)
def _no_real_network(monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError("real network call in test; rig httpx first")

    monkeypatch.setattr(httpx, "get", explode)
    monkeypatch.setattr(httpx, "post", explode)
