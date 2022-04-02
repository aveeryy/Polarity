import re
from typing import List, Tuple

from polarity.config import lang
from polarity.extractor.base import ExtractorError, StreamExtractor
from polarity.types import Stream
from polarity.utils import request_json, vprint
from requests.models import Response


class LimelightExtractor(StreamExtractor):
    """
    Limelight stream extractor
    """

    HOST = r"limelight:(\w{32})"
    DEFAULTS = {"prefer_mobile": False, "preferred_format": "http_best"}
    LIMELIGHT_API_URL = "https://production-ps.lvp.llnw.net/r/PlaylistService/media"

    def __post_init__(self):
        self.id = re.match(self.HOST, self.url).group(1)

    @staticmethod
    def _rtmp_to_https(url: str) -> str:
        """
        Converts a rtmp (Real Time Messaging Protocol) url to it's https equivalent

        :param url: the rtmp url
        :return: the equivalent https url of the `url` parameter
        """
        _REPLACE = (("rtmp://", "https://"), ("s2.csl", "s2.content"))
        for a, b in _REPLACE:
            url = url.replace(a, b)

        return re.sub(r"(https://.+)(?:/.+/.+)mp(?:4|3):", r"\1/", url)

    @classmethod
    def _parse_playlist(self, playlist: dict) -> List[Stream]:
        """
        Parses a desktop playlist

        :param playlist: the raw json as a dictionary
        :return: a list of streams
        """

        def generate_stream_id(playlist: dict, stream: dict) -> str:
            protocol = "rtmp" if "rtmp" in stream["url"] else "http"
            return f"{playlist['mediaId']}[{protocol}_{int(stream['videoBitRate'])}]"

        streams = []
        for item in playlist["playlistItems"]:
            for stream in item["streams"]:
                parsed_stream = Stream(
                    url=stream["url"],
                    id=generate_stream_id(item, stream),
                    name={},  # Placeholder
                    language={},  # Placeholder
                    wanted=False,  # Placeholder
                )
                parsed_stream._limelight_bitrate = int(stream["videoBitRate"])
                parsed_stream._limelight_protocol = (
                    "rtmp" if "rtmp" in stream["url"] else "http"
                )
                streams.append(parsed_stream)

                if parsed_stream._limelight_protocol == "rtmp":
                    # Create an equivalent http(s) stream if the stream protocol is rtmp
                    converted_stream = Stream(
                        url=self._rtmp_to_https(stream["url"]),
                        name={},
                        language={},
                        wanted=False,
                        id=parsed_stream.id.replace("rtmp", "http"),
                    )

                    converted_stream._limelight_bitrate = int(stream["videoBitRate"])
                    converted_stream._limelight_protocol = "http"
                    streams.append(converted_stream)

        return streams

    @staticmethod
    def _parse_mobile_playlist(playlist: dict) -> List[Stream]:
        streams = []
        for media in playlist["mediaList"]:
            for stream in media["mobileUrls"]:
                parsed_stream = Stream(
                    url=stream["mobileUrl"],
                    name={},
                    language={},
                    wanted=False,
                    id=f"{media['mediaId']}[{stream['targetMediaPlatform']}]",
                )
                parsed_stream._limelight_protocol = stream["targetMediaPlatform"]
                streams.append(parsed_stream)
        return streams

    @staticmethod
    def _parse_closed_captions_details(details: list) -> List[Stream]:
        streams = []

        for stream in details:
            parsed_stream = Stream(
                url=stream["webvttFileUrl"],
                name={},
                language=stream["languageCode"],
                wanted=True,
                id=f"subt_{stream['languageCode']}",
            )
            streams.append(parsed_stream)
        return streams

    @classmethod
    def _call_api(self, identifier: str, request: str) -> Tuple[dict, Response]:
        """ """
        json, response = request_json(f"{self.LIMELIGHT_API_URL}/{identifier}/{request}")
        if response.status_code != 200 and "error" in json:
            vprint(
                lang["extractor"]["generic_error"] % json["error"], "error", "limelight"
            )
        return json, response

    def get_streams(self, id: str = None) -> List[Stream]:
        identifier = self.id if hasattr(self, "id") else id
        if identifier is None:
            raise ExtractorError("an identifier is required")
        streams = []  # List of parsed streams
        _METHODS = (
            self._parse_playlist,  # Playlist
            self._parse_mobile_playlist,  # MobilePlaylist
            self._parse_closed_captions_details,  # ClosedCaptionsDetails
        )

        for i, request in enumerate(
            ("Playlist", "MobilePlaylist", "ClosedCaptionsDetails")
        ):
            json, request = self._call_api(identifier, f"get{request}ByMediaId")
            if request.status_code == 200:
                # execute the corresponding method with the json as the
                # parameter, only if the request is successful
                streams.extend(_METHODS[i](json))

        _streams = [
            (s, s._limelight_bitrate)
            for s in streams
            if hasattr(s, "_limelight_protocol") and s._limelight_protocol == "http"
        ]

        # TODO: add support to set wanted stream to alternative formats
        max_stream = max(_streams, key=lambda x: x[1])
        max_stream[0].wanted = True

        return streams
