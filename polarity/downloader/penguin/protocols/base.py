class StreamProtocol():
    def __init__(self, url=str, options=dict):
        self.url = url
        self.segment_list = []
        self.options = options