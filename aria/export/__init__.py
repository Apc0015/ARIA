"""Export and output generation."""
from aria.engine.output.exporter import Exporter
from aria.engine.output.report import generate_report

class ReportGenerator:
    """Thin wrapper around generate_report for backward compatibility."""
    def generate(self, documents, topic, output_dir, stats=None):
        from pathlib import Path
        return generate_report(documents, topic, Path(output_dir), stats)

__all__ = ["Exporter", "ReportGenerator", "generate_report"]
