from polarity.downloader.protocols.base import StreamProtocol
from polarity.downloader.protocols.dash import MPEGDASHStream
from polarity.downloader.protocols.file import FileProtocol
from polarity.downloader.protocols.hls import HTTPLiveStream

ALL_PROTOCOLS = [HTTPLiveStream, MPEGDASHStream, FileProtocol]
