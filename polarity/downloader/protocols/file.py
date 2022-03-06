from polarity.downloader.protocols import StreamProtocol

from polarity.types.stream import Segment, SegmentPool


class FileProtocol(StreamProtocol):

    SUPPORTED_EXTENSIONS = r".+"

    def process(self) -> SegmentPool:
        """
        Processes the stream
        """

        pseudosegment = Segment(
            self.url,
            number=0,
            key=None,
            duration=0,
            init=False,
        )

        return SegmentPool(
            segments=[pseudosegment], format="unified", id="unified0", track_id=None
        )
