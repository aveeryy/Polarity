import pytest

from polarity.types.ffmpeg import FFmpegCommand, FFmpegInput, VIDEO, AUDIO, SUBTITLES

command = FFmpegCommand(
    "example.mkv",
    preinput_arguments=[],
    metadata_arguments=["-metadata", 'encoding_tool="Polarity"', "-c", "copy"],
)

inputs = [
    FFmpegInput(
        "video.mp4",
        track_count={VIDEO: 1, AUDIO: 2, SUBTITLES: 1},
        codecs={VIDEO: "copy", AUDIO: ["copy", "ac3"]},
        metadata={
            VIDEO: {"language": "es", "title": '"my movie.mov"'},
            AUDIO: {"language": "en"},
        },
    ),
    FFmpegInput(
        "audio.m4a",
        track_count={VIDEO: 0, AUDIO: 2},
        codecs={AUDIO: ["mp3", ""]},
        metadata={
            AUDIO: {"language": ["fr", "it"]},
        },
    ),
    FFmpegInput(
        "audio.wav",
        track_count={VIDEO: 0, AUDIO: 1},
        codecs={AUDIO: "flac"},
        metadata={
            AUDIO: {"language": "ja"},
        },
    ),
]

# add the inputs
command.extend(inputs)


@pytest.mark.parametrize(
    "command, processed",
    [
        (
            command,
            [
                "ffmpeg",
                "-i",
                "video.mp4",
                "-i",
                "audio.m4a",
                "-i",
                "audio.wav",
                "-metadata",
                'encoding_tool="Polarity"',
                "-c",
                "copy",
                "-map",
                "0:v?",
                "-map",
                "0:a?",
                "-map",
                "0:s?",
                "-c:v:0",
                "copy",
                "-c:a:0",
                "copy",
                "-c:a:1",
                "ac3",
                "-metadata:s:v:0",
                "language=es",
                "-metadata:s:v:0",
                'title="my movie.mov"',
                "-metadata:s:a:0",
                "language=en",
                "-metadata:s:a:1",
                "language=en",
                "-map",
                "1:v?",
                "-map",
                "1:a?",
                "-map",
                "1:s?",
                "-c:a:2",
                "mp3",
                "-c:a:3",
                "",
                "-metadata:s:a:2",
                "language=fr",
                "-metadata:s:a:3",
                "language=it",
                "-map",
                "2:v?",
                "-map",
                "2:a?",
                "-map",
                "2:s?",
                "-c:a:4",
                "flac",
                "-metadata:s:a:4",
                "language=ja",
                "example.mkv",
            ],
        )
    ],
)
def test_build_command(command: FFmpegCommand, processed: list):
    assert command.build() == processed
