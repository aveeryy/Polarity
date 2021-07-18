from .extractor import *
from .Polarity import Polarity
from polarity.update import selfupdate
from .version import __version__

update = selfupdate

version = __version__