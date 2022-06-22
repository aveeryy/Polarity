import re
import sys

from polarity.utils import FormattedText as FT

LINE_REGEX = r"(?P<time>.+) -> (?P<head>\[[\w]+(/(?P<level>.+)|)\]) (?P<msg>.+)"
COLORS = {
    "info": FT.green,
    "warning": FT.yellow,
    "error": FT.red,
    "fatal": FT.red,
    "exception": FT.red,
    "debug": FT.cyan,
}


def prettify(lines: list) -> str:
    prettified_log = ""

    for num, line in enumerate(lines):
        match = re.match(LINE_REGEX, line)
        if match is None:
            raise Exception(f"failed to parse line {num + 1}")
        groups = match.groupdict()
        level = groups["level"].split("/")[-1] if groups["level"] is not None else "info"
        prettified_log += f"{FT.dimmed}{groups['time']} -> {FT.reset}{COLORS[level]}{FT.bold}{groups['head']}{FT.reset} {groups['msg']}\n"

    return prettified_log


def main():
    if len(sys.argv) < 2:
        raise Exception("you need to specify a log file to open")

    with open(sys.argv[1]) as fp:
        log = fp.readlines()

    print(prettify(log))


if __name__ == "__main__":
    main()
