from dataclasses import dataclass, field
from .base import MediaType, MetaMediaType


@dataclass
class FFmpegInput(MediaType, metaclass=MetaMediaType):
    input_path: str
    indexes: dict
    codecs: dict
    metadata: dict = field(default_factory=dict)
    hls_stream: bool = False

    def generate_command(self) -> dict:
        """
        Generates part of a ffmpeg command, split in two parts

        * Input

        Contains the input files and allowed_extensions

        * Meta

        Contains the stream codecs and metadata

        If multiple FFmpegInput objects are used, first join the input
        part of the command, then the metadata and last the output
        """
        command = {"input": [], "meta": []}
        if self.hls_stream:
            command["input"] += "-allowed_extensions", "ALL"
        command["input"] += "-i", self.input_path

        command["meta"] += "-map", f'{self.indexes["file"]}:{VIDEO}?'
        command["meta"] += "-map", f'{self.indexes["file"]}:{AUDIO}?'
        command["meta"] += "-map", f'{self.indexes["file"]}:{SUBTITLES}?'
        for media_type, codec in self.codecs.items():
            command["meta"] += f"-c:{media_type}:{self.indexes[media_type]}", codec
        for media_type, metadata in self.metadata.items():
            for key, value in metadata.items():
                if value is None:
                    continue
                if type(value) == list:
                    value = value[self.indexes[media_type]]
                command["meta"] += (
                    f"-metadata:s:{media_type}:{self.indexes[media_type]}",
                    f"{key}={value}",
                )
        return command


VIDEO = "v"
AUDIO = "a"
SUBTITLES = "s"
