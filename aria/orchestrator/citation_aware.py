"""Wrapper orchestrator that adds citation expansion to the main pipeline.

Extends MasterOrchestrator with post-collection citation graph expansion phase.
"""

from __future__ import annotations

import asyncio
from typing import Any

from aria.orchestrator.citation_expansion import CitationPipeline, CitationExpansionConfig
from aria.orchestrator.master import MasterOrchestrator


class CitationAwareMasterOrchestrator:
    """Wraps MasterOrchestrator to add citation expansion phase."""

    def __init__(self, config: Any, logger: Any):
        """Initialize wrapper.

        Args:
            config: ARIA configuration object
            logger: Logger instance
        """
        self.master = MasterOrchestrator(config, logger)
        self.logger = logger

    async def run(
        self,
        mission: dict[str, Any],
        collect_only: bool = False,
        clean_only: bool = False,
        validate_credentials: bool = False,
        authenticated_only: bool = False,
        public_only: bool = False,
        resume: bool = False,
        credentials_path: str | None = None,
        raw_dir: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Run research with optional citation expansion phase.

        Args:
            mission: Mission configuration dict
            collect_only: Skip cleaning and export
            clean_only: Skip collection
            validate_credentials: Validate and exit
            authenticated_only: Filter to authenticated sources
            public_only: Filter to public sources
            resume: Resume interrupted run
            credentials_path: Path to credentials file
            raw_dir: Raw data directory
            **kwargs: Additional orchestrator arguments

        Returns:
            RunResult with collected and citation-expanded documents
        """
        # Run normal orchestrator pipeline
        result = await self.master.run(
            mission=mission,
            collect_only=collect_only,
            clean_only=clean_only,
            validate_credentials=validate_credentials,
            authenticated_only=authenticated_only,
            public_only=public_only,
            resume=resume,
            credentials_path=credentials_path,
            **({"raw_dir": raw_dir} if raw_dir else {}),
            **kwargs,
        )

        # Skip citation expansion if:
        # - credentials-only validation
        # - clean-only mode
        # - already exported/cleaning stage (skip would have completed)
        if validate_credentials or clean_only:
            return result

        # Check if citation expansion enabled in mission
        citation_config_dict = mission.get("citation_expansion", {})
        if not citation_config_dict.get("enabled", False):
            return result

        try:
            # Load collected documents from raw storage
            collected_docs = self._load_raw_documents(result)

            if not collected_docs:
                self.logger.info("[Citation] No documents to expand")
                return result

            self.logger.info(f"[Citation] Starting expansion of {len(collected_docs)} documents")

            # Configure citation expansion
            citation_config = CitationExpansionConfig(
                enabled=True,
                max_depth=citation_config_dict.get("max_depth", 2),
                max_citations_per_paper=citation_config_dict.get(
                    "max_citations_per_paper", 20
                ),
                max_concurrent_fetches=citation_config_dict.get(
                    "max_concurrent_fetches", 5
                ),
                only_academic=citation_config_dict.get("only_academic", True),
            )

            # Run citation expansion
            pipeline = CitationPipeline(citation_config)
            expansion_result = await pipeline.run_expansion_phase(
                collected_docs, result.run_id if hasattr(result, "run_id") else "unknown"
            )

            # Save expanded documents to raw storage
            expanded_docs = expansion_result["new_documents"]
            if expanded_docs:
                self._save_raw_documents(result, expanded_docs)
                self.logger.info(f"[Citation] Added {len(expanded_docs)} cited papers")

            # Update stats
            if hasattr(result, "stats") and isinstance(result.stats, dict):
                result.stats["citation_expansion"] = expansion_result["stats"]
                result.stats["documents_expanded"] = len(expanded_docs)

        except Exception as exc:
            self.logger.warning(f"[Citation] Expansion failed (continuing): {exc}")
            # Don't fail the entire run due to citation expansion issues
            # Citation expansion is optional enhancement

        return result

    def _load_raw_documents(self, result: Any) -> list[dict[str, Any]]:
        """Load documents from raw storage in result."""
        try:
            # Try accessing raw_dir from result
            if hasattr(result, "raw_dir"):
                raw_dir = result.raw_dir
            elif hasattr(result, "paths") and "raw" in result.paths:
                raw_dir = result.paths["raw"]
            else:
                return []

            # Load JSONL documents from raw directory
            from pathlib import Path
            import json

            raw_path = Path(raw_dir)
            if not raw_path.exists():
                return []

            documents = []
            for jsonl_file in raw_path.glob("*.jsonl"):
                with open(jsonl_file) as f:
                    for line in f:
                        if line.strip():
                            try:
                                documents.append(json.loads(line))
                            except json.JSONDecodeError:
                                pass

            return documents
        except Exception:
            return []

    def _save_raw_documents(self, result: Any, documents: list[dict[str, Any]]) -> None:
        """Save documents to raw storage in result."""
        try:
            if hasattr(result, "raw_dir"):
                raw_dir = result.raw_dir
            elif hasattr(result, "paths") and "raw" in result.paths:
                raw_dir = result.paths["raw"]
            else:
                return

            from pathlib import Path
            import json

            raw_path = Path(raw_dir)
            raw_path.mkdir(parents=True, exist_ok=True)

            # Append to citations.jsonl
            citations_file = raw_path / "citations.jsonl"
            with open(citations_file, "a") as f:
                for doc in documents:
                    f.write(json.dumps(doc) + "\n")

        except Exception:
            pass
