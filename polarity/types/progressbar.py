import sys

import tqdm
from polarity.config import options
from polarity.utils import FormattedText


class ProgressBar(tqdm.tqdm):
    """
    Progress bar with a small head identifier, based on tqdm, for tasks
    >>> ProgressBar(head='download', desc='Series S01E01', ...)
    [download] Series S01E01 |     | 0% 0.03MB/1.43GB[00:12>01:03:32, 31.49kb/s]
    """

    def __init__(
        self,
        iterable=None,
        desc=None,
        total=None,
        leave=True,
        file=None,
        ncols=None,
        mininterval=0.1,
        maxinterval=10,
        miniters=None,
        disable=False,
        unit="it",
        unit_scale=False,
        smoothing=0.3,
        bar_format=None,
        initial=0,
        position=None,
        postfix=None,
        unit_divisor=1000,
        write_bytes=None,
        lock_args=None,
        nrows=None,
        colour=None,
        delay=0,
        gui=False,
        head=None,
        **kwargs,
    ):

        if options["verbose"] == "quiet":
            # do not show progress bars while quiet
            return

        if head is not None:
            desc = f"{FormattedText.magenta}{FormattedText.bold}[{head}]{FormattedText.reset} {desc}"  # noqa

        super().__init__(
            iterable=iterable,
            desc=desc,
            total=total,
            leave=leave,
            file=file,
            ncols=ncols,
            mininterval=mininterval,
            maxinterval=maxinterval,
            miniters=miniters,
            ascii=sys.platform == "win32",
            disable=disable,
            unit=unit,
            unit_scale=unit_scale,
            dynamic_ncols=True,
            smoothing=smoothing,
            bar_format=bar_format,
            initial=initial,
            position=position,
            postfix=postfix,
            unit_divisor=unit_divisor,
            write_bytes=write_bytes,
            lock_args=lock_args,
            nrows=nrows,
            colour=colour,
            delay=delay,
            gui=gui,
            **kwargs,
        )
