from typing import List

from polarity.downloader.protocols import StreamProtocol
from polarity.types.stream import Segment, SegmentPool
from polarity.utils import request_webpage


class FileProtocol(StreamProtocol):
    """
    ### FileProtocol class

    Supports non-playlist files. Tries to split files into segments
    if web server accepts byte ranges, else downloads the whole
    file in one go

    Support type: `Full (internal)`

    #### Resources
    * [Accept-Ranges header (MDN)](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Accept-Ranges)
    * [Range header (MDN)](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Range)
    """

    SUPPORTED_EXTENSIONS = r".+"

    def calculate_ranges(self, content_size: int) -> List[str]:
        """
        Calculate byte ranges for segments

        :param content_size: File size in bytes
        :yield: byte ranges
        """
        content_size = int(content_size)  # file size in bytes
        current = -1  # the initial range size
        end = False  # stops range generation if True
        while True:
            # split the file in 1 MiB segments
            final = current + (1024 ** 2)
            if final > content_size:
                # avoid requesting invalid bytes
                final = content_size
                end = True
            yield f"{current + 1}-{final}"
            if end:
                return
            current += 1024 ** 2

    def process(self) -> List[SegmentPool]:
        """
        Processes the stream
        """
        segments = []
        # make a request to check if we can split the file
        # into segments
        request = request_webpage(self.url, "head")
        # Check if web server accepts byte ranges
        if (
            "Accept-Ranges" in request.headers
            # Make sure we also have a content length header
            and "Content-Length" in request.headers
            and request.headers["Accept-Ranges"] == "bytes"
        ):
            for n, range in enumerate(
                self.calculate_ranges(request.headers["Content-Length"])
            ):
                segment = Segment(self.url, number=n, byte_range=range)
                segments.append(segment)

        else:
            # Web server does not accept byte ranges, download the whole
            # file in one go, will mess up the progress bar and download resuming
            # of this file, but probably won't matter if it's a small file, like
            # subtitles or small audio tracks
            segments = [Segment(self.url, 0)]

        return [SegmentPool(segments=segments, media_type="unified", pool_type="file")]
