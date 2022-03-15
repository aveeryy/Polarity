import json
import os
import re
import subprocess
import sys
import threading
from copy import deepcopy
from dataclasses import asdict
from random import choice
from shutil import move
from time import sleep
from typing import List
from urllib.parse import unquote

from polarity.config import lang, paths
from polarity.downloader.base import BaseDownloader
from polarity.downloader.protocols import ALL_PROTOCOLS
from polarity.types import Content, ProgressBar, Thread
from polarity.types.ffmpeg import AUDIO, SUBTITLES, VIDEO, FFmpegCommand, FFmpegInput
from polarity.types.stream import ContentKey, M3U8Pool, Segment, SegmentPool, Stream
from polarity.utils import (
    dict_merge,
    get_extension,
    mkfile,
    request_webpage,
    strip_extension,
    thread_vprint,
    vprint,
)
from polarity.version import __version__


class PenguinSignals:
    """
    Signals for communication between segment downloaders and/or
    PenguinDownloader threads
    """

    PAUSE = 0
    STOP = 1


class PenguinDownloader(BaseDownloader):

    thread_lock = threading.Lock()

    ARGUMENTS = [
        {
            "args": ["--penguin-threads"],
            "attrib": {"help": lang["penguin"]["args"]["threads"]},
            "variable": "threads",
        },
        {
            "args": ["--penguin-tag-output"],
            "attrib": {},
            "variable": "tag_output",
        },
    ]

    DEFAULTS = {
        "attempts": 10,
        "threads": 5,
        # Add a metadata entry with the Polarity version
        "tag_output": False,
        # Delete segments as these are merged to the final file
        # 'delete_merged_segments': True,
        "ffmpeg": {
            "codecs": {
                "video": "copy",
                "audio": "copy",
                # Changing this is not recommended, specially with Crunchyroll
                # since it uses SSA subtitles with styles, converting those to
                # SRT will cause them to lose all formatting
                # Instead make a codec rule with the source format's extension
                # and the desired codec
                "subtitles": "copy",
            },
            "codec_rules": {
                ".vtt": [["subtitles", "srt"]],
            },
        },
        "tweaks": {
            # Fixes Atresplayer subtitles italic parts
            "atresplayer_subtitle_fix": True,
            # Converts ttml2 subtitles to srt with internal convertor
            # "convert_ttml2_to_srt": True,
        },
    }

    _SIGNAL = {}

    def __init__(self, item: Content, _options=None, _stack_id: int = 0) -> None:
        super().__init__(item, _stack_id=_stack_id, _options=_options)

        self.threads = []

        self.output_data = {
            "inputs": [],
            "segment_pools": [],
            "pool_count": {
                "video": 0,
                "audio": 0,
                "subtitles": 0,
                "unified": 0,
            },
            "total_segments": 0,
            "binary_concat": False,
        }

        self.resume_stats = {
            "downloaded_bytes": 0,
            "total_bytes": 0,
            "downloaded_segments": [],
        }
        # Convert values to integers
        self.options["penguin"]["threads"] = int(self.options["penguin"]["threads"])
        self.hooks = {"download_update": [self._download_progress_hook]}
        if "hooks" in self.options:
            dict_merge(
                self.hooks,
                self.options["hooks"],
                overwrite=True,
                modify=True,
                extend_lists=True,
            )

    def _start(self):
        super()._start()
        can_resume = False

        # Check if the download can be resumed from a previous session
        if os.path.exists(f"{self.temp_path}/pools.json"):
            # Load the output data
            output_data = self.load_output_data()
            if output_data is None:
                # Output data has failed to load, delete the file and do the
                # pre-processing again
                vprint(lang["penguin"]["output_file_broken"], "error", "penguin")
                # Remove the file
                os.remove(f"{self.temp_path}/pools.json")
            elif type(output_data) is dict:
                vprint(
                    lang["penguin"]["resuming"] % self.content["name"],
                    module_name="penguin",
                )
                self.output_data = output_data
                can_resume = True
                # Load the download stats
                if os.path.exists(f"{self.temp_path}/stats.json"):
                    self.resume_stats = self.load_resume_stats()

        if not can_resume:
            # We either can't resume or it's a new download
            for stream in self.streams:
                for pool in self.process_stream(stream):
                    # get an identifier for the segment pool
                    identifier = self.generate_pool_id(pool.media_type)
                    pool.set_id(identifier)
                    if pool.pool_type == M3U8Pool:
                        # Create a m3u8 playlist to later merge the segments
                        playlist = self.create_m3u8_playlist(pool)
                        mkfile(f"{self.temp_path}/{pool._id}.m3u8", playlist)
                    # Create a ffmpeg input from the pool and stream
                    ffmpeg_input = self.create_input(pool, stream)
                    self.output_data["segment_pools"].append(pool)
                    self.output_data["inputs"].append(ffmpeg_input)
                    self.output_data["total_segments"] += len(pool.segments)

            # Save pools to file
            self.save_output_data()

        # Create segment downloaders
        vprint(
            lang["penguin"]["threads_started"] % (self.options["penguin"]["threads"]),
            module_name="penguin",
            level="debug",
        )

        self.progress_bar = ProgressBar(
            head="download",
            desc=self.content["name"],
            total=0,
            initial=self.resume_stats["downloaded_bytes"],
            unit="ib",
            unit_scale=True,
            leave=False,
        )
        self._last_updated = self.resume_stats["downloaded_bytes"]

        # Create the download threads
        for i in range(self.options["penguin"]["threads"]):
            thread_name = f"{threading.current_thread().name}/{i}"
            thread = Thread(target=self.segment_downloader, name=thread_name, daemon=True)
            self.threads.append(thread)
            thread.start()

        # Wait until threads stop
        while True:
            # Check if seg. downloaders have finished
            if not [t for t in self.threads if t.is_alive()]:
                self.progress_bar.close()
                self.resume_stats["download_finished"] = True
                break
            sleep(1)

        # Remux all the tracks together
        command = self.generate_ffmpeg_command()
        # Create a watchdog thread and start it
        watchdog = Thread("__FFmpeg_Watchdog", target=self.ffmpeg_watchdog)
        watchdog.start()
        # Run ffmpeg and wait until watchdog has returned
        subprocess.run(command, check=True)
        while watchdog.is_alive():
            sleep(0.1)
        # Cleanup, close the progress bar, move the output file to it's final
        # destination and remove all temporal files and directories
        self.remux_bar.close()
        move(f"{self.temp_path}{get_extension(self.output)}", f"{self.output}")
        # Remove temporal files
        for file in os.scandir(f'{paths["tmp"]}{self.content["sanitized"]}'):
            os.remove(file.path)
        os.rmdir(f"{self.temp_path}")

        self.success = True

    def save_output_data(self) -> None:
        # Clone the output data dictionary
        data = deepcopy(self.output_data)
        # Convert segment pools to dictionaries
        data["segment_pools"] = [asdict(p) for p in data["segment_pools"]]
        data["inputs"] = [asdict(p) for p in data["inputs"]]
        mkfile(f"{self.temp_path}/pools.json", json.dumps(data, indent=4), overwrite=True)

    def load_output_data(self) -> dict:
        with open(f"{self.temp_path}/pools.json", "r") as f:
            # Load the output data from the file
            try:
                output = json.load(f)
            except json.decoder.JSONDecodeError:
                return
        pools = []
        inputs = []
        for pool in output["segment_pools"]:
            segments = []

            for segment in pool["segments"]:
                # Convert to Segment objects
                # Create the content key from the dictionary data
                key = (
                    {
                        "video": ContentKey(**segment["key"]["video"])
                        if segment["key"]["video"] is not None
                        else None,
                        "audio": ContentKey(**segment["key"]["audio"])
                        if segment["key"]["audio"] is not None
                        else None,
                    }
                    if segment["key"] is not None
                    else None
                )
                # Delete the key from the loaded data
                # This avoids SyntaxError exceptions, due to duplicate args
                segment = {
                    k: v
                    for k, v in segment.items()
                    if not k.startswith("_") and k != "key"
                }
                # Create the segment from the content key and dict data
                _segment = Segment(key=key, **segment)
                # Add segment to temporal list
                segments.append(_segment)
            # Delete the segment list from the loaded data
            del pool["segments"]
            _pool = SegmentPool(segments=segments, **pool)
            _pool.set_id(_pool.media_type)
            # Add pool to temporal list
            pools.append(_pool)
        for _input in output["inputs"]:
            inp = FFmpegInput(**_input)
            inputs.append(inp)
        output["segment_pools"] = pools
        output["inputs"] = inputs
        return output

    def save_resume_stats(self) -> None:
        mkfile(
            f"{self.temp_path}/stats.json",
            json.dumps(self.resume_stats, indent=4),
            overwrite=True,
        )

    def load_resume_stats(self) -> dict:
        path = f"{self.temp_path}/stats.json"
        with open(path, "rb") as f:
            try:
                return json.load(f)
            except json.decoder.JSONDecodeError:
                vprint(lang["penguin"]["resume_file_broken"], "error", "penguin")
                return self._recreate_resume_stats()

    def _recreate_resume_stats(self) -> dict:
        vprint(lang["penguin"]["resume_file_recreation"], module_name="penguin")
        stats = {
            "downloaded_bytes": 0,
            "total_bytes": 0,
            "downloaded_segments": [],
        }
        for file in os.scandir(self.temp_path):
            if get_extension(file.name) in (".m3u8",):
                continue
            stats["downloaded_segments"].append(strip_extension(file.name))
            stats["downloaded_bytes"] += file.stat().st_size

        # Calculate total bytes
        stats["total_bytes"] = (
            stats["downloaded_bytes"]
            / len(stats["downloaded_segments"])
            * self.output_data["total_segments"]
        )
        return stats

    # Pre-processing

    def generate_pool_id(self, pool_format: str) -> str:
        """
        Generates an unique pool identifier from the inputted string

        :param pool_format: The pool format to generate the id for
        :return: The generated identifier
        """
        pool_id = f'{pool_format}{self.output_data["pool_count"][pool_format]}'

        self.output_data["pool_count"][pool_format] += 1
        return pool_id

    def _download_progress_hook(self, content: dict) -> None:
        """ """
        if content["signal"] != "downloaded_segment":
            return
        self.resume_stats["downloaded_bytes"] += content["size"]
        self.resume_stats["downloaded_segments"].append(content["segment"])
        # Update the total byte estimate
        size = self.calculate_final_size(
            self.resume_stats["downloaded_bytes"],
            len(self.resume_stats["downloaded_segments"]),
            self.output_data["total_segments"],
        )
        self.resume_stats["total_bytes"] = size
        # Notify hooks of updated download size
        self._execute_hooks("download_update", {"signal": "updated_size", "size": size})
        self.save_resume_stats()
        # Update progress bar
        self.progress_bar.total = size
        self.progress_bar.update(
            self.resume_stats["downloaded_bytes"] - self._last_updated
        )
        self._last_updated = self.resume_stats["downloaded_bytes"]

    def process_stream(self, stream: Stream) -> List[SegmentPool]:
        """
        Get segments from a stream

        :param stream: A Stream object to parse, with it's parameter `wanted`
        being True
        :return: A list of SegmentPools, one for each track, sometimes video and
        audio are together, those are considered `unified` tracks
        """
        if not stream.wanted:
            return []
        vprint(lang["penguin"]["processing_stream"] % stream.id, "debug", "penguin")
        for protocol in ALL_PROTOCOLS:
            if not re.match(protocol.SUPPORTED_EXTENSIONS, get_extension(stream.url)):
                continue
            vprint(
                lang["penguin"]["stream_protocol"] % (protocol.__name__, stream.id),
                "debug",
            )
            pools = protocol(stream=stream, options=self.options).process()
            if stream.extra_audio:
                media_type = "audio"
            elif stream.extra_sub:
                media_type = "subtitles"
            else:
                media_type = "unified"
            for pool in pools:
                pool.media_type = media_type
            return pools

    def create_input(self, pool: SegmentPool, stream: Stream) -> FFmpegInput:
        def set_metadata(parent: str, child: str, value: str):
            if parent not in ff_input.metadata:
                ff_input.metadata[parent] = {}
            if value is None or not value:
                return
            elif type(value) is list:
                value = value.pop(0)
            elif type(value) is dict:
                if parent in value:
                    value = value[parent]
                elif pool._id in value:
                    value = value[pool._id]
                else:
                    return
                # check if value is now a list and has items
                if type(value) is list and value:
                    value = value.pop(0)

            ff_input.metadata[parent][child] = value

        TRACK_COUNT = {
            "unified": {VIDEO: 1, AUDIO: 1},
            VIDEO: {VIDEO: 1},
            AUDIO: {AUDIO: 1},
            SUBTITLES: {SUBTITLES: 1},
        }

        pool_extension = (
            pool.pool_type if pool.pool_type is not None else pool.get_ext_from_segment()
        )
        segment_extension = pool.get_ext_from_segment(0)
        if pool_extension in (".m3u", ".m3u8"):
            path = f"{self.temp_path}/{pool._id}{pool_extension}"
        # TODO: improve this
        elif pool.pool_type == "file":
            path = f"concat:{'|'.join([self.temp_path + '/' + i._filename for i in pool.segments])}"
        else:
            path = f"{self.temp_path}/{pool._id}_0{pool_extension}"

        ff_input = FFmpegInput(
            path=path,
            track_count=TRACK_COUNT[pool.media_type],
            codecs=dict(self.options["penguin"]["ffmpeg"]["codecs"]),
            metadata={},
        )

        if pool.media_type in ("video", "unified"):
            set_metadata(VIDEO, "title", stream.name)
            set_metadata(VIDEO, "language", stream.language)
        if pool.media_type in ("audio", "unified"):
            set_metadata(AUDIO, "title", stream.name)
            set_metadata(AUDIO, "language", stream.language)
        if pool.media_type == "subtitles":
            set_metadata(SUBTITLES, "title", stream.name)
            set_metadata(SUBTITLES, "language", stream.language)

        for ext, rules in self.options["penguin"]["ffmpeg"]["codec_rules"].items():
            if ext == segment_extension:
                proc = {rule[0]: rule[1] for rule in rules}
                codec_rules = {**ff_input.codecs, **proc}
                ff_input.codecs = codec_rules
                break
        return ff_input

    def create_m3u8_playlist(self, pool: SegmentPool) -> str:
        """
        Creates a m3u8 playlist from a SegmentPool's segments.

        :param pool: The SegmentPool object to generate the playlist
        :return: A m3u8 playlist
        """

        def download_key(segment: Segment) -> None:
            vprint(lang["penguin"]["key_download"] % segment._id, "debug")
            key_contents = request_webpage(url=unquote(segment.key["video"].url))

            mkfile(
                f"{self.temp_path}/{pool._id}_{key_num}.key",
                contents=key_contents.content,
                writing_mode="wb",
            )

        s = "/" if sys.platform != "win32" else "\\"
        last_key = None
        key_num = 0
        # Playlist header
        playlist = "#EXTM3U\n#EXT-X-PLAYLIST-TYPE:VOD\n#EXT-X-MEDIA-SEQUENCE:0\n"

        # Handle initialization segments
        init_segment = [f for f in pool.segments if f.init]
        if init_segment:
            init_segment = init_segment[0]
            playlist += f'#EXT-X-MAP:URI="{init_segment._filename}"\n'

        # Add segments to playlist
        for segment in pool.segments:
            if segment.key != last_key and segment.key is not None:
                if segment.key["video"] is not None:
                    last_key = segment.key
                    key_path = f"{self.temp_path}{s}{pool._id}_{key_num}.key"
                    if sys.platform == "win32":
                        key_path = key_path.replace("\\", "\\\\")
                    playlist += f'#EXT-X-KEY:METHOD={segment.key["video"].method},URI="{key_path}"\n'  # noqa: E501
                    # Download the key
                    download_key(segment)
                    key_num += 1
            playlist += (
                f"#EXTINF:{segment.duration},\n{self.temp_path}/{segment._filename}\n"
            )
        # Write end of file
        playlist += "#EXT-X-ENDLIST\n"

        return playlist

    @staticmethod
    def calculate_final_size(
        downloaded_bytes: float, downloaded_segments: int, total_segments: int
    ) -> float:
        """
        Calculates final output size

        :param downloaded_bytes:
        :return: Estimation of end size in bytes (not the type)
        """
        if downloaded_segments == 0:
            # Avoid dividing by 0
            return 0
        return downloaded_bytes / downloaded_segments * total_segments

    ###################
    # Post-processing #
    ###################

    def ffmpeg_watchdog(self):
        """
        Watch FFmpeg merge progress

        :return: Nothing
        """

        stats = {
            "total_size": 0,
            "out_time": None,
            "progress": "continue",
        }

        last_update = 0
        self.remux_bar = ProgressBar(
            head="remux",
            desc=self.content["name"],
            unit="iB",
            unit_scale=True,
            leave=False,
            total=self.resume_stats["downloaded_bytes"],
        )
        # Wait until file is created
        while not os.path.exists(f"{self.temp_path}/ffmpeg.txt"):
            sleep(0.5)
        while stats["progress"] == "continue":
            with open(f"{self.temp_path}/ffmpeg.txt", "r") as f:
                try:
                    # Read the last 15 lines
                    data = f.readlines()[-15:]
                    for i in ("total_size", "out_time", "progress"):
                        pattern = re.compile(f"{i}=(.+)")
                        # Find all matches
                        matches = re.findall(pattern, "\n".join(data))
                        stats[i] = matches[-1].split(".")[0]
                except IndexError:
                    sleep(0.2)
                    continue
            self.remux_bar.update(int(stats["total_size"]) - last_update)
            last_update = int(stats["total_size"])
            sleep(0.5)

    def generate_ffmpeg_command(self) -> list:
        """
        Generates a ffmpeg command from the output data's inputs

        :return: The ffmpeg command as a list
        """
        # Merge segments
        command = FFmpegCommand(
            f"{paths['tmp']}{self.content['sanitized']}{get_extension(self.output)}",
            preinput_arguments=[
                "-v",
                "error",
                "-y",
                "-protocol_whitelist",
                "file,crypto,data,http,https,tls,tcp,concat",
            ],
            metadata_arguments=[
                "-progress",
                f"{self.temp_path}/ffmpeg.txt",
            ],
        )

        if self.options["penguin"]["tag_output"]:
            command.metadata_arguments.extend(
                ["-metadata", f"encoding_tool=Polarity {__version__} with Penguin"]
            )

        command.extend(self.output_data["inputs"])

        return command.build()

    def segment_downloader(self):
        """
        ## Segment downloader

        First, takes tries to take an unreserved segment pool; if
        all pools have already been reserved by other threads, take one at random

        Then pops a segment from the pool and attempts to download it, if successful,
        writes it's data into a file and updates the progress bar among other stuff
        """

        def get_pool() -> SegmentPool:
            def get_unfinished_pools() -> List[SegmentPool]:
                return [p for p in self.output_data["segment_pools"] if not p._finished]

            def get_unreserved_pools() -> List[SegmentPool]:
                return [p for p in self.output_data["segment_pools"] if not p._reserved]

            unfinished = get_unfinished_pools()
            pools = get_unreserved_pools()
            if not unfinished:
                return
            if not pools:
                pool = choice(unfinished)
                thread_vprint(
                    lang["penguin"]["assisting"] % (pool._reserved_by, pool._id),
                    level="verbose",
                    module_name=thread_name,
                    lock=self.thread_lock,
                )
                return pool
            pools[0]._reserved = True
            pools[0]._reserved_by = thread_name
            return pools[0]

        thread_name = threading.current_thread().name

        thread_vprint(
            message=lang["penguin"]["thread_started"] % thread_name,
            module_name="penguin",
            level="debug",
            lock=self.thread_lock,
        )

        while True:
            # Grab a segment pool
            pool = get_pool()

            if pool is None:
                return

            thread_vprint(
                lang["penguin"]["current_pool"] % pool._id,
                level="verbose",
                module_name=thread_name,
                lock=self.thread_lock,
            )
            while True:
                if not pool.segments:
                    pool._finished = True
                    break
                segment = pool.segments.pop(0)
                segment_path = f"{self.temp_path}/{segment._filename}"
                if segment._id in self.resume_stats["downloaded_segments"]:
                    # segment has already been downloaded, skip
                    thread_vprint(
                        message=lang["penguin"]["segment_skip"] % segment._id,
                        module_name=thread_name,
                        level="verbose",
                        lock=self.thread_lock,
                    )
                    continue

                thread_vprint(
                    message=lang["penguin"]["segment_start"] % segment._id,
                    module_name=thread_name,
                    level="verbose",
                    lock=self.thread_lock,
                )

                size = 0

                for i in range(self.options["penguin"]["attempts"]):
                    try:
                        segment_data = request_webpage(
                            segment.url,
                            method="get",
                            timeout=15,
                            headers={"range": f"bytes={segment.byte_range}"}
                            if segment.byte_range is not None
                            else {},
                        )
                        # TODO: better exception handling
                        # TODO: better messaging, add retries
                    except BaseException as ex:
                        thread_vprint(
                            lang["penguin"]["except"]["download_fail"]
                            % (segment._id, ex),
                            module_name=thread_name,
                            level="exception",
                            lock=self.thread_lock,
                        )
                        sleep(0.5)
                        continue
                    if "Content-Length" in segment_data.headers:
                        size = int(segment_data.headers["Content-Length"])
                    segment_contents = segment_data.content

                    if (
                        segment._ext == ".vtt"
                        and self.options["penguin"]["tweaks"]["atresplayer_subtitle_fix"]
                    ):
                        segment_contents = self.fix_vtt(segment_contents)
                    # TODO: better ttml2 implementation, since previous
                    # one can lose formatting

                    # Write fragment data to file
                    mkfile(segment_path, segment_contents, False, "wb")
                    thread_vprint(
                        lang["penguin"]["segment_downloaded"] % segment._id,
                        level="verbose",
                        module_name=thread_name,
                        lock=self.thread_lock,
                    )
                    segment._finished = True

                    self._execute_hooks(
                        "download_update",
                        {
                            "signal": "downloaded_segment",
                            "content": self.content["extended"],
                            "segment": segment._id,
                            "size": size,
                        },
                    )

                    # handle signaling
                    # TODO: better testing of signal sending and checking
                    signals = self.check_signal()
                    if signals:
                        # Since there can be multiple signals,
                        # for example: one global and one
                        #  take the first signal
                        signal = signals[0]
                        # if signal is stop, return
                        if signal == PenguinSignals.STOP:
                            return
                        # if signal is pause, halt execution
                        # until signal is cleared
                        if signal == PenguinSignals.PAUSE:

                            while self.get_signal()[0] == PenguinSignals.PAUSE:
                                sleep(0.2)

                    break

    @staticmethod
    def fix_vtt(data: bytes) -> bytes:
        """
        Workaround for Atresplayer subtitles, fixes italic characters and
        aposthrophes

        :param data: The subtitle file data
        :return: Subtitle file data with fixes applied
        """
        # Fix italic characters
        # Replace facing (#) characters
        data = re.sub(r"^# ", "<i>", data.decode(), flags=re.MULTILINE)
        # Replace trailing (#) characters
        data = re.sub(r" #$", "</i>", data, flags=re.MULTILINE)
        # Fix aposthrophes and encode the data back
        return data.replace("&apos;", "'").encode()

    def check_signal(self) -> int:
        """Check if a signal has been sent to this PenguinDownloader object"""
        return [x for x in ("all", self._thread_id) if x in self._SIGNAL]
