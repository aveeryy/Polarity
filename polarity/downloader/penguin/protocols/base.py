class StreamProtocol:
    def __init__(self, url=str, options=dict):
        self.url = url
        self.segment_pools = []
        self.options = options