from __future__ import annotations

from aria.brain.expander import QueryExpander


class _DummyBrain:
    def __init__(self, *_args, **_kwargs):
        return None


def test_expander_class_exists():
    assert QueryExpander is not None
