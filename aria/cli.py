"""CLI entry point for ARIA."""

from __future__ import annotations

import argparse
import sys


VERSION = "ARIA 5.0.0"


def build_parser() -> argparse.ArgumentParser:
    """Build the ARIA CLI parser."""
    parser = argparse.ArgumentParser(
        prog="aria",
        description="ARIA: Agentic Research Intelligence Architecture",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  aria --serve-api\n"
            "  aria --topic 'quantum computing' --output-dir ./results\n"
            "  aria --mission missions/research.yaml\n"
            "  aria --mission missions/research.yaml --clean-only --raw-dir ./data/raw\n"
            "  aria --validate-credentials\n"
        ),
    )

    # ── Run modes ──────────────────────────────────────────────────────────
    mode_group = parser.add_argument_group("run modes")
    mode_group.add_argument(
        "--serve-api",
        action="store_true",
        help="Start the FastAPI server for ARIA Studio.",
    )
    mode_group.add_argument(
        "--topic",
        type=str,
        metavar="TOPIC",
        help="Quick research run on a topic string.",
    )
    mode_group.add_argument(
        "--mission",
        type=str,
        metavar="FILE",
        help="Run from a mission YAML file.",
    )
    mode_group.add_argument(
        "--validate-credentials",
        action="store_true",
        help="Validate configured credentials and exit.",
    )

    # ── Run flags ──────────────────────────────────────────────────────────
    flags_group = parser.add_argument_group("run flags")
    flags_group.add_argument(
        "--clean-only",
        action="store_true",
        help="Skip collection; clean existing raw data only.",
    )
    flags_group.add_argument(
        "--raw-dir",
        type=str,
        metavar="DIR",
        help="Path to existing raw data directory (used with --clean-only).",
    )
    flags_group.add_argument(
        "--resume",
        action="store_true",
        help="Resume an interrupted run.",
    )

    # ── Output ─────────────────────────────────────────────────────────────
    output_group = parser.add_argument_group("output")
    output_group.add_argument(
        "--output-dir",
        type=str,
        metavar="DIR",
        help="Output directory for results.",
    )
    output_group.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging.",
    )

    # ── API server options ─────────────────────────────────────────────────
    server_group = parser.add_argument_group("API server options")
    server_group.add_argument(
        "--api-host",
        type=str,
        default="0.0.0.0",
        help="Host for the API server (default: 0.0.0.0).",
    )
    server_group.add_argument(
        "--api-port",
        type=int,
        default=8765,
        help="Port for the API server (default: 8765).",
    )

    # ── Meta ───────────────────────────────────────────────────────────────
    parser.add_argument(
        "--version",
        action="version",
        version=VERSION,
    )

    return parser


def _run_research(args: argparse.Namespace) -> int:
    """Execute a research run via MasterOrchestrator."""
    from pathlib import Path

    try:
        import asyncio
        from aria.config import load_config
        from aria.utils.logger import configure_logging
    except ImportError as exc:
        print(f"[aria] Error: failed to import ARIA core modules: {exc}", file=sys.stderr)
        return 1

    # Try main orchestrator first (with citation support), fall back if not available
    MasterOrchestrator = None
    try:
        from aria.orchestrator.citation_aware import CitationAwareMasterOrchestrator
        MasterOrchestrator = CitationAwareMasterOrchestrator
    except ImportError:
        pass
    except Exception as exc:
        print(f"[aria] Warning: citation-aware orchestrator unavailable: {exc}", file=sys.stderr)

    # Fall back to standard orchestrator
    if MasterOrchestrator is None:
        try:
            from aria.orchestrators.master import MasterOrchestrator  # type: ignore[assignment]
        except ImportError:
            try:
                from aria.orchestrator.master import MasterOrchestrator  # type: ignore[assignment]
            except ImportError as exc:
                print(
                    f"[aria] Error: backend (aria.engine) is not installed.\n"
                    f"       Run: pip install aria.engine\n"
                    f"       Details: {exc}",
                    file=sys.stderr,
                )
                return 1

    output_dir = Path(args.output_dir) if args.output_dir else None
    config = load_config(output_dir=output_dir)
    logger = configure_logging(verbose=args.verbose)

    # Build mission dict
    mission: dict = {}
    if args.mission:
        try:
            from aria.mission import load_mission_file_or_args
            mission = load_mission_file_or_args(args.mission, args.topic)
        except ImportError:
            try:
                from aria.mission import load_mission_text
                mission = load_mission_text(Path(args.mission).read_text(encoding="utf-8"))
            except Exception as exc:
                print(f"[aria] Error loading mission file '{args.mission}': {exc}", file=sys.stderr)
                return 1
    elif args.topic:
        try:
            from aria.mission import build_mission_from_args
            mission = build_mission_from_args(args.topic)
        except ImportError:
            from aria.mission import apply_defaults, validate_mission
            mission = validate_mission(apply_defaults({"collection": {"topic": args.topic}}))

    if not mission and not args.validate_credentials:
        print("[aria] Error: provide --topic or --mission to start a run.", file=sys.stderr)
        return 1

    raw_dir = Path(args.raw_dir) if getattr(args, "raw_dir", None) else None

    orchestrator = MasterOrchestrator(config, logger)

    async def _run():
        return await orchestrator.run(
            mission,
            collect_only=False,
            clean_only=bool(args.clean_only),
            validate_credentials=bool(args.validate_credentials),
            authenticated_only=False,
            public_only=False,
            resume=bool(args.resume),
            credentials_path=str(config.credentials_file),
            **({"raw_dir": str(raw_dir)} if raw_dir else {}),
        )

    try:
        result = asyncio.run(_run())
        if args.verbose:
            print(f"[aria] Run complete. Stats: {result.stats}")
        return 0
    except KeyboardInterrupt:
        print("\n[aria] Interrupted.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"[aria] Run failed: {exc}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def main() -> int:
    """Execute the CLI command."""
    parser = build_parser()
    args = parser.parse_args()

    # ── Serve API ───────────────────────────────────────────────────────────
    if args.serve_api:
        try:
            import uvicorn
        except ImportError:
            print("[aria] Error: uvicorn is not installed. Run: pip install uvicorn", file=sys.stderr)
            return 1

        print(f"[aria] Starting ARIA API Server on http://{args.api_host}:{args.api_port}")
        print(f"[aria] API Docs: http://{args.api_host}:{args.api_port}/docs")
        print(f"[aria] Health:   http://{args.api_host}:{args.api_port}/api/health")

        uvicorn.run(
            "aria.api.app:app",
            host=args.api_host,
            port=args.api_port,
            reload=False,
        )
        return 0

    # ── Research run (topic / mission / validate-credentials) ───────────────
    if args.topic or args.mission or args.validate_credentials:
        return _run_research(args)

    # ── No command – show help ──────────────────────────────────────────────
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
