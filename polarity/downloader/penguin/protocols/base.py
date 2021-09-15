from polarity.types.stream import Stream


class StreamProtocol:
    def __init__(self, stream: Stream, options=dict):
        self.stream = stream
        self.url = stream.url
        self.segment_pools = []
        self.options = options