from __future__ import annotations

import sys

from pandapower_agent.cli.dispatch import dispatch
from pandapower_agent.cli.parser import build_parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return dispatch(args, parser=parser)


if __name__ == "__main__":
    sys.exit(main())
