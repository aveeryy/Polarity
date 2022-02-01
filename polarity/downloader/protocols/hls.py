from m3u8 import parse
from requests.adapters import HTTPAdapter
from urllib.parse import urljoin
from urllib3.util.retry import Retry

from polarity.config import lang
from polarity.downloader.protocols.base import StreamProtocol
from polarity.types.stream import Stream, Segment, SegmentPool, ContentKey, M3U8Pool
from polarity.types.ffmpeg import VIDEO, AUDIO, SUBTITLES
from polarity.utils import vprint, request_webpage


class HTTPLiveStream(StreamProtocol):
    SUPPORTED_EXTENSIONS = (".m3u", ".m3u8")

    def open_playlist(self):
        self.manifest_data = request_webpage(self.url).content
        self.parsed_data = parse(self.manifest_data.decode())
        self.processed_tracks = {VIDEO: 0, AUDIO: 0, "unified": 0, SUBTITLES: 0}
        if self.parsed_data["is_variant"]:
            # Get preferred resolution stream
            self.resolutions = [
                (
                    s,
                    int(
                        s["stream_info"]["resolution"].split("x")[1]
                        if "resolution" in s["stream_info"]
                        else 0
                    ),
                )
                for s in self.parsed_data["playlists"]
            ]
            self.resolution = min(
                self.resolutions, key=lambda x: abs(x[1] - self.options["resolution"])
            )
            self.streams = [s for s in self.resolutions if s[1] == self.resolution[1]]
            # Pick higher bitrate stream
            if len(self.streams) > 1:
                self.bandwidth_values = [
                    s[0]["stream_info"]["bandwidth"] for s in self.streams
                ]
                self._stream = self.streams[
                    self.bandwidth_values.index(max(self.bandwidth_values))
                ][0]
            else:
                self._stream = self.streams[0][0]
        else:
            self._stream = self.parsed

    def get_stream_fragments(self, stream=dict, force_type=None, only_subtitles=False):
        def build_segment_pool(media_type=str):
            self.processed_tracks[media_type] += 1
            if media_type == "unified":
                self.processed_tracks[VIDEO] += 1
                self.processed_tracks[AUDIO] += 1

            segments = [
                # Create a Segment object
                Segment(
                    url=urljoin(self.stream_url, s["uri"]),
                    number=self.parsed_stream["segments"].index(s),
                    media_type=media_type,
                    key={
                        "video": ContentKey(s["key"]["uri"], None, s["key"]["method"])
                        if "key" in s
                        else None,
                        "audio": ContentKey(s["key"]["uri"], None, s["key"]["method"])
                        if "key" in s
                        else None,
                    },
                    group=f"{media_type}{self.processed_tracks[media_type] - 1}",
                    duration=s["duration"],
                    init=False,
                    byte_range=None,
                )
                for s in self.parsed_stream["segments"]
            ]

            l = 0
            for segment in segments:
                segment.time = l
                l += segment.duration

            seg_pool = SegmentPool(
                segments,
                media_type,
                f"{media_type}{self.processed_tracks[media_type]}",
                None,
                M3U8Pool,
            )
            return seg_pool

        def create_init_segment(pool: str) -> None:
            self.segment_pool.segments.append(
                Segment(
                    url=urljoin(
                        self.stream_url, self.parsed_stream["segment_map"]["uri"]
                    ),
                    number=-1,  # number -1 is reserved for the init segment
                    init=True,
                    media_type=pool,
                    duration=None,
                    key=None,
                    group=f"{pool}{self.processed_tracks[pool] - 1}",
                    byte_range=None,
                )
            )

        self.stream_url = urljoin(self.url, stream["uri"])
        vprint(lang["penguin"]["protocols"]["getting_stream"], "debug", "penguin/hls")
        self.stream_data = request_webpage(self.stream_url).content
        self.parsed_stream = parse(self.stream_data.decode())
        # Support for legacy m3u8 playlists
        # (Not having video and audio in different streams)
        if not only_subtitles:
            if force_type is not None:
                self.segment_pool = build_segment_pool(force_type)
                if "segment_map" in self.parsed_stream:
                    create_init_segment(pool=force_type)
                self.segment_pools.append(self.segment_pool)
                return

            if "audio" not in stream["stream_info"]:
                self.segment_pool = build_segment_pool("unified")
                if "segment_map" in self.parsed_stream:
                    create_init_segment(pool="unified")
            else:
                self.segment_pool = build_segment_pool("video")
            self.segment_pools.append(self.segment_pool)
            if "segment_map" in self.parsed_stream:
                create_init_segment(pool="video")

        for media in self.parsed_data["media"]:
            if media["type"] == "AUDIO" and not only_subtitles:
                self.get_stream_fragments(media, "audio")
            elif media["type"] == "SUBTITLES":
                # Process "external" subtitles
                if ".m3u" in media["uri"]:
                    self.get_stream_fragments(media, "subtitles")
                else:
                    contents = request_webpage(urljoin(self.url, media["uri"])).content
                    # Fuck whoever thought it was a good idea to disguise
                    # m3u8 playlists as .vtt subtitles
                    if b"#EXTM3U" in contents:
                        self.get_stream_fragments(media, "subtitles")
                        continue
                    self.processed_tracks["subtitles"] += 1
                    subtitles = Segment(
                        url=urljoin(self.url, media["uri"]),
                        number=0,
                        type="subtitles",
                        group=f'subtitles{self.processed_tracks["subtitles"]}',
                    )
                    subtitle_pool = SegmentPool(
                        [subtitles],
                        format="subtitles",
                        id=f"subtitles{self.processed_tracks['subtitles']}",
                        track_id=None,
                        pool_type=None,
                    )

                    self.segment_pools.append(subtitle_pool)

    def extract(self):

        vprint(
            lang["penguin"]["protocols"]["getting_playlist"],
            "debug",
            module_name="penguin/hls",
        )

        self.open_playlist()
        self.get_stream_fragments(self._stream, only_subtitles=self.stream.extra_sub)
        return {"segment_pools": self.segment_pools, "tracks": self.processed_tracks}
