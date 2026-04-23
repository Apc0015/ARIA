"""ArXiv collector wrapper."""
from aria.engine.collectors.academic.core import AcademicCollector

class ArxivCollector(AcademicCollector):
    """ArXiv-only academic collector."""
    def __init__(self, max_results=20):
        super().__init__(max_per_source=max_results, sources=["arxiv"])
