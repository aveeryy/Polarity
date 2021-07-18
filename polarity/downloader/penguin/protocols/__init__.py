from .hls import HTTPLiveStream

class TestMode:
    '''
    ## Penguin
    ### Test Mode
    Launches Penguin in test mode, allowing for individual functions to be tested
    '''
    def __init__(self, url):
        pass

    @staticmethod
    def extract_frags():
        pass

    SUPPORTED_EXTENSIONS = ('.test_mode')

ALL_PROTOCOLS = [HTTPLiveStream, TestMode]