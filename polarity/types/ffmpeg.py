from dataclasses import dataclass, field
from typing import Union, List, Dict

from polarity.types.base import MediaType, MetaMediaType
from polarity.utils import get_extension


@dataclass
class FFmpegInput(MediaType, metaclass=MetaMediaType):
    """
    FFmpegInput object

    Defines a FFmpeg input as an object, is appended to a FFmpegCommand
    object using the later's .append() method

    :param path: Input file path
    :param track_count: Dictionary with the track type as the key
    and the number of those tracks as the value
    :param metadata: Dictionary with metadata
    :param codecs: Dictionary with codecs
    See docs/types/ffmpeg.md for more info
    """

    path: str
    track_count: Dict[str, int]
    metadata: dict = field(default_factory=dict)
    codecs: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        # add missing keys to track_count and metadata dicts
        self.track_count = {**{VIDEO: 0, AUDIO: 0, SUBTITLES: 0}, **self.track_count}
        self.metadata = {**{VIDEO: {}, AUDIO: {}, SUBTITLES: {}}, **self.metadata}
        # determine if stream is a hls stream
        self.hls_stream = ".m3u" in get_extension(self.path)


@dataclass
class FFmpegCommand(MediaType, metaclass=MetaMediaType):
    """
    ## FFmpegCommand object

    Defines a FFmpeg command, inputs are added using the `.append()` method

    The command is divided in 4 parts: pre-inputs, inputs, metadata, output
    * `pre-input`

    General arguments, example: `ffmpeg -v debug -y`
    * `inputs`

    File inputs and their arguments, example: `-allowed_extensions ALL -i <file>`
    * `metadata`

    Track metadata and codecs, example: `-metadata title="cookies" -c:v libx264`
    * `output`

    Output path
    """

    output: str
    preinput_arguments: list = field(default_factory=list)
    metadata_arguments: list = field(default_factory=list)
    inputs: List[FFmpegInput] = field(init=False, default_factory=list)

    def append(self, _input: FFmpegInput) -> None:
        """Append and FFmpegInput object to the command"""
        self.inputs.append(_input)

    def extend(self, _input: FFmpegInput) -> None:
        self.inputs.extend(_input)

    def build(self, as_string=False) -> Union[List[str], str]:
        """
        Returns a valid FFmpeg command from the inputs' data
        :param as_string: returns the command as a string
        :returns: command as a list unless as_string is True
        """

        # set the command base
        main_arguments = [
            "ffmpeg",
            # add user arguments
            *self.preinput_arguments,
        ]
        # set the base for metadata arguments
        metadata_arguments = [*self.metadata_arguments]
        indexes = {"file": 0, VIDEO: 0, AUDIO: 0, SUBTITLES: 0}
        for inp in self.inputs:
            # *-- Input part --*#
            if inp.hls_stream:
                # allow decryption of .m3u* streams
                main_arguments.extend(("-allowed_extensions", "ALL"))
            main_arguments.extend(("-i", f"{inp.path}"))
            # *-- Metadata part --*#
            metadata_arguments.extend(
                # make sure that only video, audio and subtitle tracks
                # are remuxed into the final file
                sum([["-map", f"{indexes['file']}:{x}?"] for x in ("v", "a", "s")], [])
            )

            # convert non-list to list objects
            inp.codecs = {
                k: [v] * inp.track_count[k] if type(v) is str else v
                for k, v in inp.codecs.items()
            }

            # same as above
            for track_type in (VIDEO, AUDIO, SUBTITLES):
                inp.metadata[track_type] = {
                    k: [v] * inp.track_count[track_type] if type(v) is str else v
                    for k, v in inp.metadata[track_type].items()
                }

            # add the codec arguments
            metadata_arguments.extend(
                # add the codecs
                sum(
                    [
                        [f"-c:{t[0]}:{indexes[t] + i}", c]
                        # t: track type
                        # cs: codecs
                        for t, cs in inp.codecs.items()
                        # i: index relative to file
                        # c: codec
                        for i, c in enumerate(cs)
                    ],
                    [],
                )
            )

            # add the metadata arguments
            metadata_arguments.extend(
                sum(
                    [
                        [f"-metadata:s:{t[0]}:{indexes[t] + i}", f"{k}={v}"]
                        # t: track type
                        # m: metadata
                        for t, m in inp.metadata.items()
                        # k: metadata keys
                        # vs: metadata values
                        for k, vs in m.items()
                        # i: index of track relative to file
                        # v: metadata value
                        for i, v in enumerate(vs)
                    ],
                    [],
                )
            )
            # increase index count
            # adds input's stream count to index dictionary
            indexes["file"] += 1
            indexes = {
                k: indexes.get(k, 0) + inp.track_count.get(k, 0) for k in set(indexes)
            }

        # append the metadata arguments
        main_arguments.extend(metadata_arguments)
        # append the output
        main_arguments.append(self.output)

        if as_string:
            return " ".join(main_arguments)
        return main_arguments


VIDEO = "video"
AUDIO = "audio"
SUBTITLES = "subtitles"
