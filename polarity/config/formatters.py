import argparse
import sys

from polarity.lang import lang


class HelpFormatter(argparse.HelpFormatter):
    """The default, minimal help formatter"""

    class _Section(object):
        def __init__(self, formatter, parent, heading=None):
            self.formatter = formatter
            self.parent = parent
            self.heading = heading
            self.items = []

        def format_help(self):
            # format the indented section
            if self.parent is not None:
                self.formatter._indent()
            join = self.formatter._join_parts
            item_help = join([func(*args) for func, args in self.items])
            if self.parent is not None:
                self.formatter._dedent()

            # return nothing if the section was empty
            if not item_help:
                return ""

            # add the heading if the section was non-empty
            if self.heading != "==SUPRESS==" and self.heading is not None:
                current_indent = self.formatter._current_indent
                heading = "%*s%s\n%s\n" % (
                    current_indent + 1,
                    "",
                    # Bold header
                    f"\033[1m{self.heading}\033[0m",
                    # Underline
                    "\u2500" * (len(self.heading) + 2),
                )
            else:
                heading = ""

            # join the section-initial newline, the heading and the help
            return join(["\n", heading, item_help, "\n"])

    def _format_usage(self, usage, actions, groups, prefix) -> str:
        # Change the usage text to the language provided one
        prefix = f"\033[1m{lang['polarity']['use']}\033[0m"
        return super()._format_usage(usage, actions, groups, prefix)

    def _format_text(self, text: str) -> str:
        # Make the text below the usage string bold
        return super()._format_text(f"\033[1m{text}\033[0m")

    def _format_action_invocation(self, action):
        return ", ".join(action.option_strings)


class ExtendedFormatter(HelpFormatter):
    """A more verbose help formatter, showing argument's possible values"""

    def _format_args(self, action, default_metavar):
        get_metavar = self._metavar_formatter(action, default_metavar)
        if action.nargs is None:
            result = "%s" % get_metavar(1)
        elif action.nargs == argparse.OPTIONAL:
            result = "[%s]" % get_metavar(1)
        elif action.nargs == argparse.ZERO_OR_MORE:
            metavar = get_metavar(1)
            result = "[%s ...]" % metavar
        elif action.nargs == argparse.ONE_OR_MORE:
            result = "%s ..." % get_metavar(1)
        elif action.nargs == argparse.REMAINDER:
            result = "..."
        elif action.nargs == argparse.PARSER:
            result = "%s ..." % get_metavar(1)
        elif action.nargs == argparse.SUPPRESS:
            result = ""
        else:
            try:
                formats = ["%s" for _ in range(action.nargs)]
            except TypeError:
                raise ValueError("invalid nargs value") from None
            result = " ".join(formats) % get_metavar(action.nargs)
        return result

    def _metavar_formatter(self, action, default_metavar):
        if action.metavar is not None:
            result = action.metavar
        if action.choices is not None:
            choice_strs = [str(choice) for choice in action.choices]
            result = "(%s)" % ",".join(choice_strs)
        else:
            result = ""

        def format(tuple_size):
            if isinstance(result, tuple):
                return result
            else:
                return (result,) * tuple_size

        return format

    def _format_action_invocation(self, action):
        if not action.option_strings or action.nargs == 0:
            return super()._format_action_invocation(action)
        default = self._get_default_metavar_for_optional(action)
        args_string = self._format_args(action, default)
        return ", ".join(action.option_strings) + " " + args_string


# Set preferred help formatter
formatter = HelpFormatter if "--extended-help" not in sys.argv else ExtendedFormatter
