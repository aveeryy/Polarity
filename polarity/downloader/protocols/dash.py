from typing import List
from urllib.parse import urljoin

from polarity.lang import lang
from polarity.downloader.protocols.base import StreamProtocol
from polarity.types.stream import Segment, SegmentPool
from polarity.utils import request_xml, vprint


class MPEGDASHProtocol(StreamProtocol):
    """
    ### MPEGDASHStream Protocol class

    Gives support for MPEG-DASH (Dynamic Adaptive Streaming over HTTP)
    streams to Penguin.

    Support type: `Experimental (internal parser)`

    Supported extensions:
    * .mpd

    #### Resources
    * [Wikipedia page](https://en.wikipedia.org/wiki/Dynamic_Adaptive_Streaming_over_HTTP)
    """

    SUPPORTED_EXTENSIONS = r"\.mpd"

    def parse_playlist(self) -> List[SegmentPool]:
        def process_audio_repr(repr: dict):
            if "@audioTrackId" in adap_set:
                id_entry = adap_set["@audioTrackId"]
            elif "@lang" in adap_set:
                id_entry = adap_set["@lang"]
            if id_entry not in audio_bitrate:
                audio_bitrate[id_entry] = (None, 0)
            # Small workaround to add stream language to missing entries
            # Fixes missing metadata of hidden languages
            # on PrimeVideoExtractor (Singularity)
            if id_entry not in self.stream.language:
                self.stream.language[id_entry] = adap_set["@lang"]
            if int(repr["@bandwidth"]) > int(audio_bitrate[id_entry][1]):
                audio_bitrate[id_entry] = (repr, int(repr["@bandwidth"]))

        segment_pools = []
        # key is the audio track identifier
        # value is a tuple of the track and the bitrate / bandwidth
        audio_bitrate = {}
        self.manifest_data = request_xml(self.url)[0]

        for adap_set in self.manifest_data["MPD"]["Period"]["AdaptationSet"]:
            if (
                "@contentType" in adap_set
                and adap_set["@contentType"] == "video"
                or "@mimeType" in adap_set
                and "video" in adap_set["@mimeType"]
            ):
                vprint(
                    lang["penguin"]["protocols"]["picking_best_stream_0"],
                    "debug",
                    "penguin/dash",
                )
                resolution_list = [
                    (r, int(r["@height"])) for r in adap_set["Representation"]
                ]
                # Get the resolution that closer matches the desired one
                resolution = min(
                    resolution_list, key=lambda x: abs(x[1] - self.options["resolution"])
                )
                # Get the streams with the chosen resolution
                streams = [s for s in resolution_list if s[1] == resolution[1]]
                # Pick stream with higher bitrate (bandwidth value)
                if len(streams) > 1:
                    vprint(
                        lang["penguin"]["protocols"]["picking_best_stream_1"],
                        "debug",
                        "penguin/dash",
                    )
                    bandwidth_values = [int(s[0]["@bandwidth"]) for s in streams]
                    stream = streams[bandwidth_values.index(max(bandwidth_values))][0]
                else:
                    # Desired resolution does not have multiple streams
                    stream = streams[0][0]
                stream_id = stream["BaseURL"] if "BaseURL" in stream else stream["@id"]
                vprint(
                    lang["penguin"]["protocols"]["selected_stream"] % stream_id,
                    "debug",
                    "penguin/dash",
                )
                # Get the stream segments
                segment_pools.append(self.get_stream_segments(stream, "video"))
            elif (
                "@contentType" in adap_set
                and adap_set["@contentType"] == "audio"
                or "@mimeType" in adap_set
                and "audio" in adap_set["@mimeType"]
            ):
                vprint(
                    lang["penguin"]["protocols"]["picking_best_stream_2"],
                    "debug",
                    "penguin/dash",
                )
                if type(adap_set["Representation"]) == list:
                    for repr in adap_set["Representation"]:
                        process_audio_repr(repr)
                else:
                    process_audio_repr(adap_set["Representation"])

        for _, repr in audio_bitrate.items():
            segment_pools.append(self.get_stream_segments(repr[0], "audio"))

        return segment_pools

    def get_stream_segments(
        self, representation: dict, media_type="unified"
    ) -> SegmentPool:
        """
        Get the segments from a representation entry of the playlist

        :param representation: Representation entry of the AdaptationSet
        :param media_type: Media type of the Representation entry, defaults
        to "unified" (combined video and audio)
        :return: SegmentPool from the parsed segments
        """

        def parse_byte_ranged_stream() -> SegmentPool:
            # Build the stream url from the playlist url and the base
            stream_url = urljoin(self.url, representation["BaseURL"])
            vprint(
                lang["penguin"]["protocols"]["getting_stream"], "debug", "penguin/dash"
            )

            segment_pool = SegmentPool(
                segments=[
                    # Create a Segment object
                    Segment(
                        url=stream_url,
                        number=list(representation["SegmentList"]["SegmentURL"]).index(s),
                        byte_range=s["@mediaRange"],
                    )
                    for s in representation["SegmentList"]["SegmentURL"]
                ],
                media_type=media_type,
                pool_type="dash",
            )

            # Create an initialization segment, if exists
            if "Initialization" in representation["SegmentList"]:
                init_segment = Segment(
                    url=stream_url,
                    number=-1,
                    init=True,
                    byte_range=representation["SegmentList"]["Initialization"]["@range"],
                )
                segment_pool.segments.append(init_segment)
            return segment_pool

        def parse_second_ranged_stream() -> SegmentPool:
            # TODO
            raise NotImplementedError
            segment_pool = SegmentPool()
            return segment_pool

        if "BaseURL" in representation:
            return parse_byte_ranged_stream()
        return parse_second_ranged_stream()

    def process(self) -> List[SegmentPool]:
        """Process the given stream"""
        vprint(
            lang["penguin"]["protocols"]["getting_playlist"],
            "debug",
            module_name="penguin/dash",
        )
        return self.parse_playlist()
