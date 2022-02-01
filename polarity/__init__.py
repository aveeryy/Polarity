import io
import logging
import sys

logging.Logger(__name__)
logging.getLogger(__name__).setLevel(10)
__log_capture = io.StringIO()
# create a temporal handler to capture config vprint statements
__handler = logging.StreamHandler(__log_capture)
__handler.setLevel(10)
logging.getLogger(__name__).addHandler(__handler)

from polarity.config import paths  # noqa
from polarity.utils import filename_datetime  # noqa

AVOID_RUNNING = ["pytest", "black"]

# avoid creating an empty log file if vscode pytest's
# test discovery is triggered
if not [x for x in AVOID_RUNNING if x in sys.argv]:
    # Set logging filename and configuration
    log_filename = paths["log"] + f"log_{filename_datetime()}.log"
    # create log file with the temporary handler output as a base
    with open(log_filename, "w") as fp:
        fp.write(__log_capture.getvalue())
    # remove the temporary handler
    logging.getLogger(__name__).removeHandler(__handler)
    # create and add the new handler
    log_handler = logging.FileHandler(log_filename, mode="a")
    # set handler debug level to maximum
    log_handler.setLevel(10)
    logging.getLogger(__name__).addHandler(log_handler)

# cleanup the temporary handler stuff
__log_capture.close()
del __log_capture
del __handler

from .Polarity import Polarity  # noqa
