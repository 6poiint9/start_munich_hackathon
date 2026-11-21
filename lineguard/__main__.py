"""Command line entry point: `python -m lineguard <command>`.

Commands:
    init        create the database of the workspace and apply migrations
    run         start the API and the agents
    import      load the files of the source once and compute the state
    recompute   compute the state again from the stored facts
    reread      read files again whose path contains a text
    send-logged send the mails that DRY_RUN only logged (needs MAIL_MODE=LIVE)
    demo-save   store the current state as the demo start state
    demo-reset  restore the demo start state
"""

import argparse
import sys

from lineguard import config


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lineguard", description=__doc__,
                                     formatter_class=argparse.RawTextHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    run = commands.add_parser("run")
    run.add_argument("--port", type=int, default=8000)
    run.add_argument("--no-agents", action="store_true")
    load = commands.add_parser("import")
    load.add_argument("--no-llm", action="store_true",
                      help="wave 1 only: tables, no documents")
    evaluate = commands.add_parser("eval")
    evaluate.add_argument("pack", nargs="?")
    commands.add_parser("recompute")
    reread = commands.add_parser("reread")
    reread.add_argument("text", help="part of the file path")
    commands.add_parser("send-logged")
    commands.add_parser("demo-save")
    commands.add_parser("demo-reset")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Runs one command and returns the process exit code."""
    config.load_dotenv()
    args = _build_parser().parse_args(argv)
    # Imported here so that `--help` works before the pack is configured.
    from lineguard import commands  # pylint: disable=import-outside-toplevel

    return commands.run(args)


if __name__ == "__main__":
    sys.exit(main())
