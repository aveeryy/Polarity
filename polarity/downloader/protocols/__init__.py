from .base import StreamProtocol
from .hls import HTTPLiveStream
from .dash import MPEGDASHStream


class TestMode:
    """
    ## Penguin
    ### Test Mode
    Launches Penguin in test mode, allowing for individual functions to be tested
    """

    def __init__(self, url):
        pass

    @staticmethod
    def extract_frags():
        pass

    SUPPORTED_EXTENSIONS = ".test_mode"


ALL_PROTOCOLS = [HTTPLiveStream, MPEGDASHStream, TestMode]

SUPPORTED = [ext for protocol in ALL_PROTOCOLS for ext in protocol.SUPPORTED_EXTENSIONS]
