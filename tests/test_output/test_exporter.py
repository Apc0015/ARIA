from __future__ import annotations

import json

from aria.output.exporter import Exporter


def test_exporter_writes_json_with_ensemble_fields(tmp_path):
    exporter = Exporter(tmp_path)
    path = exporter.export_json(
        [
            {
                "title": "Sample",
                "summary": "Summary",
                "source_url": "llm://ollama/llama3.1:8b/test",
                "source_type": "llm_response",
                "provider": "ollama",
                "model_id": "llama3.1:8b",
                "query": "test query",
                "is_comparison": False,
            }
        ]
    )
    payload = json.loads(path.read_text())
    assert payload[0]["provider"] == "ollama"
