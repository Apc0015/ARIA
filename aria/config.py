"""ARIA configuration management."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict


PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent
DATA_ROOT = PROJECT_ROOT / "data"


class Config(BaseModel):
    """ARIA configuration."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    raw_data_dir: Path = DATA_ROOT / "raw"
    clean_data_dir: Path = DATA_ROOT / "clean"
    export_dir: Path = DATA_ROOT / "exports"
    runs_dir: Path = DATA_ROOT / "runs"
    credentials_file: Path = PROJECT_ROOT / "credentials" / "credentials.json"
    session_cache_dir: Path = PROJECT_ROOT / "credentials" / "sessions"
    default_mission_file: Path = PROJECT_ROOT / "missions" / "examples" / "default.yaml"

    api_port: int = 8765
    api_host: str = "0.0.0.0"

    shared_memory_backend: str = "dict"
    redis_url: Optional[str] = None

    kb_path: Optional[Path] = None
    kb_enabled: bool = True

    gap_detection_enabled: bool = True
    knowledge_graph_enabled: bool = True
    semantic_dedup_enabled: bool = False  # opt-in — requires sentence-transformers
    smart_query_planning: bool = True
    image_extraction_enabled: bool = True
    streaming_clean: bool = False
    # Link crawl — follow outbound links from scraped web pages
    link_crawl_enabled: bool = True
    link_crawl_depth: int = 2         # 1 = direct links only; 2 = links-of-links
    link_crawl_max_per_doc: int = 2   # links to follow per source page
    link_crawl_max_total: int = 20    # hard cap across all pages in a run
    # Citation following — resolve DOI/arXiv/PMID references found in docs
    citation_following_enabled: bool = True
    citation_depth: int = 1           # 1 = direct citations only; 2 = citations-of-citations
    citation_max: int = 20            # max papers to fetch per run
    
    
    def ensure_directories(self) -> None:
        for path in [
            self.raw_data_dir,
            self.clean_data_dir,
            self.export_dir,
            self.runs_dir,
            self.session_cache_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def with_llm_override(
        self,
        provider: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> "Config":
        """Apply LLM provider overrides via env vars so downstream components pick them up."""
        import os

        if provider:
            os.environ["LLM_PROVIDER"] = provider
        if model:
            prefix = provider.upper() if provider else "LLM"
            os.environ[f"{prefix}_MODEL"] = model
        if api_key:
            prefix = provider.upper() if provider else "LLM"
            os.environ[f"{prefix}_API_KEY"] = api_key
        if base_url:
            os.environ["OLLAMA_BASE_URL"] = base_url
        return self


def load_config(output_dir: Path | None = None) -> Config:
    run_root = output_dir.expanduser().resolve() if output_dir else DATA_ROOT
    
    config = Config(
        raw_data_dir=run_root / "raw",
        clean_data_dir=run_root / "clean",
        export_dir=run_root / "exports",
        runs_dir=run_root / "runs",
        credentials_file=Path(
            os.getenv("CREDENTIALS_FILE", str(PROJECT_ROOT / "credentials" / "credentials.json"))
        ).expanduser(),
        session_cache_dir=Path(
            os.getenv("SESSION_CACHE_DIR", str(PROJECT_ROOT / "credentials" / "sessions"))
        ).expanduser(),
        default_mission_file=Path(
            os.getenv("DEFAULT_MISSION_FILE", str(PROJECT_ROOT / "missions" / "examples" / "default.yaml"))
        ).expanduser(),
        api_port=int(os.getenv("ARIA_API_PORT", "8765")),
        api_host=os.getenv("ARIA_API_HOST", "0.0.0.0"),
        shared_memory_backend=os.getenv("SHARED_MEMORY_BACKEND", "dict"),
        redis_url=os.getenv("REDIS_URL"),
        kb_path=Path(os.getenv("ARIA_KB_PATH", "~/.aria/knowledge_base/aria_kb.db")).expanduser()
            if os.getenv("ARIA_KB_PATH") else None,
        kb_enabled=os.getenv("ARIA_KB_ENABLED", "true").lower() not in ("false", "0", "no"),
        gap_detection_enabled=os.getenv("ARIA_GAP_DETECTION", "true").lower() not in ("false", "0", "no"),
        knowledge_graph_enabled=os.getenv("ARIA_KNOWLEDGE_GRAPH", "true").lower() not in ("false", "0", "no"),
        semantic_dedup_enabled=os.getenv("ARIA_SEMANTIC_DEDUP", "false").lower() in ("true", "1", "yes"),
        smart_query_planning=os.getenv("ARIA_SMART_QUERIES", "true").lower() not in ("false", "0", "no"),
        image_extraction_enabled=os.getenv("ARIA_IMAGE_EXTRACTION", "true").lower() not in ("false", "0", "no"),
        streaming_clean=os.getenv("ARIA_STREAMING_CLEAN", "false").lower() not in ("false", "0", "no"),
        link_crawl_enabled=os.getenv("ARIA_LINK_CRAWL", "true").lower() not in ("false", "0", "no"),
        link_crawl_depth=int(os.getenv("ARIA_LINK_CRAWL_DEPTH", "2")),
        link_crawl_max_per_doc=int(os.getenv("ARIA_LINK_CRAWL_PER_DOC", "2")),
        link_crawl_max_total=int(os.getenv("ARIA_LINK_CRAWL_MAX", "20")),
        citation_following_enabled=os.getenv("ARIA_CITATIONS", "true").lower() not in ("false", "0", "no"),
        citation_depth=int(os.getenv("ARIA_CITATION_DEPTH", "1")),
        citation_max=int(os.getenv("ARIA_CITATION_MAX", "20")),
    )
    
    config.ensure_directories()
    return config



load_settings = load_config
