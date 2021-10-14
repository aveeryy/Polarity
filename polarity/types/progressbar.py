from colorama import Fore

import sys
import tqdm

class ProgressBar(tqdm.tqdm):
    '''
    Progress bar with a small head identifier, based on tqdm, for tasks
    >>> ProgressBar(head='download', name='Series S01E01', ...)
    [download] Series S01E01 |     | 0% 0.03MB/1.43GB[00:12>>01:03:32, 31.49kb/s]
    '''
    
    def __init__(self, iterable=None, desc=None, total=None, leave=True, file=None, ncols=None, mininterval=0.1, maxinterval=10, miniters=None, ascii=None, disable=False, unit='it', unit_scale=False, dynamic_ncols=False, smoothing=0.3, bar_format=None, initial=0, position=None, postfix=None, unit_divisor=1000, write_bytes=None, lock_args=None, nrows=None, colour=None, delay=0, gui=False, head=None, **kwargs):
        # Set head color to magenta if platform is not Windows
        # Unsupported on Windows due to Powershell being absolute shit
        color = Fore.MAGENTA if sys.platform != 'win32' else ''
        if head is not None:
            desc = f'{color}[{head}]{Fore.RESET} {desc}'
        super().__init__(iterable=iterable, desc=desc, total=total, leave=leave, file=file, ncols=ncols, mininterval=mininterval, maxinterval=maxinterval, miniters=miniters, ascii=ascii, disable=disable, unit=unit, unit_scale=unit_scale, dynamic_ncols=dynamic_ncols, smoothing=smoothing, bar_format=bar_format, initial=initial, position=position, postfix=postfix, unit_divisor=unit_divisor, write_bytes=write_bytes, lock_args=lock_args, nrows=nrows, colour=colour, delay=delay, gui=gui, **kwargs)
            