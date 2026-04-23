"""Semantic Scholar collector wrapper."""
from aria.engine.collectors.academic.core import AcademicCollector

class SemanticScholarCollector(AcademicCollector):
    def __init__(self, max_results=20):
        super().__init__(max_per_source=max_results, sources=["semantic_scholar"])
