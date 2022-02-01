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
from typing import List, Union
from urllib.parse import unquote

from polarity.config import lang, paths
from polarity.downloader.base import BaseDownloader
from polarity.downloader.protocols import ALL_PROTOCOLS, HTTPLiveStream, MPEGDASHStream
from polarity.types import Episode, Movie, ProgressBar, Thread
from polarity.types.ffmpeg import AUDIO, SUBTITLES, VIDEO, FFmpegCommand, FFmpegInput
from polarity.types.stream import ContentKey, Segment, SegmentPool, Stream
from polarity.utils import (
    get_extension,
    mkfile,
    request_webpage,
    strip_extension,
    thread_vprint,
    vprint,
)
from polarity.version import __version__ as polarity_version

__version__ = "2022.02.01"


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
            "args": ["--penguin-segment-downloaders"],
            "attrib": {"help": lang["penguin"]["args"]["segment_downloaders"]},
            "variable": "segment_downloaders",
        }
    ]

    DEFAULTS = {
        "attempts": 10,
        "segment_downloaders": 10,
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
            "convert_ttml2_to_srt": True,
        },
    }

    _SIGNAL = {}

    def __init__(
        self,
        item: Union[Episode, Movie],
        _options=None,
        _stack_id: int = 0,
    ) -> None:
        super().__init__(item, _stack_id=_stack_id, _options=_options)

        self.segment_downloaders = []

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
            "segments_downloaded": [],
        }

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
            # Add pool to temporal list
            pools.append(_pool)
        for _input in output["inputs"]:
            inp = FFmpegInput(**_input)
            inputs.append(inp)
        output["segment_pools"] = pools
        output["inputs"] = inputs
        return output

    def save_resume_stats(self) -> None:
        if os.path.exists(f"{self.temp_path}/stats.json"):
            if os.path.exists(f"{self.temp_path}/stats.json.old"):
                os.remove(f"{self.temp_path}/stats.json.old")
            os.rename(f"{self.temp_path}/stats.json", f"{self.temp_path}/stats.json.old")
        mkfile(
            f"{self.temp_path}/stats.json",
            json.dumps(self.resume_stats, indent=4),
            overwrite=True,
        )

    def load_resume_stats(self, use_backup=False) -> dict:
        path = f"{self.temp_path}/stats.json"
        if use_backup:
            path += ".old"
        with open(path, "rb") as f:
            try:
                return json.load(f)
            except json.decoder.JSONDecodeError:
                if use_backup:
                    # Backup file also broke, return
                    vprint(
                        lang["penguin"]["resume_file_backup_broken"],
                        module_name="penguin",
                    )
                    return self.recreate_resume_stats()
                vprint(lang["penguin"]["resume_file_broken"])
                return self.load_resume_stats(True)

    def recreate_resume_stats(self) -> dict:
        vprint(lang["penguin"]["resume_file_recreation"], module_name="penguin")
        stats = {
            "downloaded_bytes": 0,
            "total_bytes": 0,
            "segments_downloaded": [],
        }
        for file in os.scandir(self.temp_path):
            if get_extension(file.name) in (".m3u8"):
                continue
            stats["segments_downloaded"].append(strip_extension(file.name))
            stats["downloaded_bytes"] += file.stat().st_size

        # Calculate total bytes
        stats["total_bytes"] = (
            stats["downloaded_bytes"]
            / len(stats["segments_downloaded"])
            * self.output_data["total_segments"]
        )
        return stats

    def _start(self):
        """
        Start the download process, first try to load resume and output data
        files if those exists, if the files are corrupted
        """
        super()._start()
        self.options["penguin"]["segment_downloaders"] = int(
            self.options["penguin"]["segment_downloaders"]
        )
        if os.path.exists(f"{self.temp_path}/pools.json"):
            # Open resume file
            output_data = self.load_output_data()
            if output_data is None:
                vprint(lang["penguin"]["output_file_broken"], "error", "penguin")
                # Remove the file
                os.remove(f"{self.temp_path}/pools.json")
            elif type(output_data) is dict:
                vprint(
                    lang["penguin"]["resuming"] % self.content["name"],
                    module_name="penguin",
                )
                self.output_data = output_data
        if not os.path.exists(f"{self.temp_path}/pools.json"):
            for stream in self.streams:
                self.process_stream(stream)

            # Save pools to file
            self.save_output_data()

        # Make a copy of the segment pools
        # Legacy stuff
        self.segment_pools = deepcopy(self.output_data["segment_pools"])
        if os.path.exists(f"{self.temp_path}/stats.json"):
            self.resume_stats = self.load_resume_stats()

        # Create segment downloaders
        vprint(
            lang["penguin"]["threads_started"]
            % (self.options["penguin"]["segment_downloaders"]),
            module_name="penguin",
            level="debug",
        )
        for i in range(self.options["penguin"]["segment_downloaders"]):
            sdl_name = f"{threading.current_thread().name}/sdl{i}"
            sdl = Thread(target=self.segment_downloader, name=sdl_name, daemon=True)
            self.segment_downloaders.append(sdl)
            sdl.start()

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

        # Wait until threads stop
        while True:

            # Update the total byte estimate
            self.resume_stats["total_bytes"] = self.calculate_final_size()

            self.save_resume_stats()

            # Update progress bar
            self.progress_bar.total = self.resume_stats["total_bytes"]
            self.progress_bar.update(
                self.resume_stats["downloaded_bytes"] - self._last_updated
            )
            self._last_updated = self.resume_stats["downloaded_bytes"]

            # Check if seg. downloaders have finished
            if not [sdl for sdl in self.segment_downloaders if sdl.is_alive()]:
                self.progress_bar.close()
                self.resume_stats["download_finished"] = True
                break

            sleep(1)

        # Remux all the tracks together
        command = self.generate_ffmpeg_command()
        watchdog = Thread("__FFmpeg_Watchdog", target=self.ffmpeg_watchdog)
        watchdog.start()
        subprocess.run(command, check=True)
        while watchdog.is_alive():
            sleep(0.1)
        self.remux_bar.close()
        move(f"{self.temp_path}.mkv", f"{self.output}.mkv")
        # Remove temporal files
        for file in os.scandir(f'{paths["tmp"]}{self.content["sanitized"]}'):
            os.remove(file.path)
        os.rmdir(f"{self.temp_path}")

        self.success = True

    # Pre-processing

    def generate_pool_id(self, pool_format: str) -> str:
        pool_id = f'{pool_format}{self.output_data["pool_count"][pool_format]}'

        self.output_data["pool_count"][pool_format] += 1
        return pool_id

    def process_stream(self, stream: Stream) -> None:
        if not stream.preferred:
            return
        vprint(lang["penguin"]["processing_stream"] % stream.id, "debug", "penguin")
        for prot in ALL_PROTOCOLS:
            if not get_extension(stream.url) in prot.SUPPORTED_EXTENSIONS:
                continue
            vprint(
                lang["penguin"]["stream_protocol"] % (prot.__name__, stream.id), "debug"
            )
            processed = prot(stream=stream, options=self.options).extract()
            for pool in processed["segment_pools"]:
                self.output_data["total_segments"] += len(pool.segments)
                pool.id = self.generate_pool_id(pool.format)
                if prot == HTTPLiveStream:
                    # Create a playlist from the segments
                    self.create_m3u8_playlist(pool=pool)
                elif prot == MPEGDASHStream and stream == self.streams[0]:
                    # TODO: rework
                    self.resume_stats["do_binary_concat"] = True
                self.output_data["segment_pools"].append(pool)
                self.output_data["inputs"].append(
                    self.create_input(
                        pool=pool, stream=stream, tracks=processed["tracks"]
                    )
                )
            return
        if not stream.extra_sub:
            vprint(lang["penguin"]["incompatible_stream"], "error", "penguin")
            return
        # Process extra subtitle streams
        subtitle_pool_id = self.generate_pool_id("subtitles")
        subtitle_pool = SegmentPool([], "subtitles", subtitle_pool_id, None, None)
        subtitle_segment = Segment(
            url=stream.url,
            number=0,
            media_type="subtitles",
            group=subtitle_pool_id,
            key=None,
            duration=None,
            init=False,
            byte_range=None,
        )
        subtitle_pool.segments = [subtitle_segment]
        self.output_data["segment_pools"].append(subtitle_pool)
        ff_input = self.create_input(
            pool=subtitle_pool, stream=stream, tracks={SUBTITLES: 1}
        )
        ff_input.path = ff_input.path.replace(subtitle_pool_id, subtitle_pool_id + "_0")
        self.output_data["inputs"].append(ff_input)

    def create_input(
        self, pool: SegmentPool, stream: Stream, tracks: dict
    ) -> FFmpegInput:
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
                elif pool.track_id in value:
                    value = value[pool.track_id]
                else:
                    return
                # check if value is now a list
                if type(value) is list:
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

        ff_input = FFmpegInput(
            path=f"{self.temp_path}/{pool.id}{pool_extension}",
            track_count=TRACK_COUNT[pool.format],
            codecs=dict(self.options["penguin"]["ffmpeg"]["codecs"]),
            metadata={},
        )

        if pool.format in ("video", "unified"):
            set_metadata(VIDEO, "title", stream.name)
            set_metadata(VIDEO, "language", stream.language)
        if pool.format in ("audio", "unified"):
            set_metadata(AUDIO, "title", stream.name)
            set_metadata(AUDIO, "language", stream.language)
        if pool.format == "subtitles":
            set_metadata(SUBTITLES, "title", stream.name)
            set_metadata(SUBTITLES, "language", stream.language)

        for ext, rules in self.options["penguin"]["ffmpeg"]["codec_rules"].items():
            if ext == segment_extension:
                proc = {rule[0]: rule[1] for rule in rules}
                codec_rules = {**ff_input.codecs, **proc}
                ff_input.codecs = codec_rules
                break
        return ff_input

    def create_m3u8_playlist(self, pool: SegmentPool) -> None:
        """
        Creates a m3u8 playlist from a SegmentPool's segments.


        """

        def download_key(segment: Segment) -> None:
            vprint(lang["penguin"]["key_download"] % segment._id, "debug")
            key_contents = request_webpage(url=unquote(segment.key["video"].url))

            mkfile(
                f"{self.temp_path}/{pool.id}_{key_num}.key",
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
                    key_path = f"{self.temp_path}{s}{pool.id}_{key_num}.key"
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
        # Write playlist to file
        mkfile(f"{self.temp_path}/{pool.id}.m3u8", playlist)

    def calculate_final_size(self) -> float:
        try:
            return (
                self.resume_stats["downloaded_bytes"]
                / len([s for s in self.resume_stats["segments_downloaded"]])
                * self.output_data["total_segments"]
            )
        except ZeroDivisionError:
            return 0

    ###################
    # Post-processing #
    ###################

    def get_segment_deletion_time(self, pools: List[SegmentPool]) -> list:
        return [
            (f"{s.group}_{s.number}{s.ext}", s.time) for p in pools for s in p.segments
        ]

    def ffmpeg_watchdog(self) -> bool:
        """
        Show FFmpeg merge progress and delete segment files as they
        are merged to the final file
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

    def generate_ffmpeg_command(
        self,
    ) -> list:
        # Merge segments
        command = FFmpegCommand(
            f"{paths['tmp']}{self.content['sanitized']}{self.options['video_extension']}",
            preinput_arguments=[
                "-v",
                "error",
                "-y",
                "-protocol_whitelist",
                "file,crypto,data,http,https,tls,tcp",
            ],
            metadata_arguments=[
                "-metadata",
                f"encoding_tool=Polarity {polarity_version} with Penguin {__version__}",
                "-progress",
                f"{self.temp_path}/ffmpeg.txt",
            ],
        )

        command.extend(self.output_data["inputs"])

        return command.build()

    def segment_downloader(self):
        def get_unfinished_pools() -> List[SegmentPool]:
            return [p for p in self.output_data["segment_pools"] if not p._finished]

        def get_unreserved_pools() -> List[SegmentPool]:
            return [p for p in self.output_data["segment_pools"] if not p._reserved]

        def get_pool() -> SegmentPool:
            unfinished = get_unfinished_pools()
            pools = get_unreserved_pools()

            if not unfinished:
                return

            if not pools:
                pool = choice(unfinished)
                vprint(
                    lang["penguin"]["assisting"] % (pool._reserved_by, pool.id),
                    "verbose",
                    thread_name,
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

            pool = get_pool()

            if pool is None:
                return

            thread_vprint(
                lang["penguin"]["current_pool"] % pool.id,
                level="verbose",
                module_name=thread_name,
                lock=self.thread_lock,
            )
            while True:
                if not pool.segments:
                    if not pool._finished:
                        pool._finished = True
                    break

                segment = pool.segments.pop(0)

                segment_path = f"{self.temp_path}/{segment._filename}"

                if segment._id in self.resume_stats["segments_downloaded"]:
                    # segment has already been downloaded, skip
                    thread_vprint(
                        message=lang["penguin"]["segment_skip"]
                        % f"{segment.group}_{segment.number}",
                        module_name=thread_name,
                        level="verbose",
                        lock=self.thread_lock,
                    )
                    continue

                thread_vprint(
                    message=lang["penguin"]["segment_start"]
                    % f"{segment.group}_{segment.number}",
                    module_name=thread_name,
                    level="verbose",
                    lock=self.thread_lock,
                )

                self.size = 0

                for i in range(1, self.options["penguin"]["attempts"]):
                    # Create a cloudscraper session
                    try:
                        segment_data = request_webpage(
                            segment.url,
                            "get",
                            timeout=15,
                            headers={"range": f"bytes={segment.byte_range}"}
                            if segment.byte_range is not None
                            else {},
                        )
                    # TODO: better exception handling
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
                        self.size = int(segment_data.headers["Content-Length"])
                        self.resume_stats["downloaded_bytes"] += self.size
                    segment_contents = segment_data.content

                    if segment._ext == ".vtt":
                        # Workarounds for Atresplayer subtitles
                        # Fix italic characters
                        # Replace facing (#) characters
                        segment_contents = re.sub(
                            r"^# ",
                            "<i>",
                            segment_contents.decode(),
                            flags=re.MULTILINE,
                        )
                        # Replace trailing (#) characters
                        segment_contents = re.sub(
                            r" #$", "</i>", segment_contents, flags=re.MULTILINE
                        )
                        # Fix aposthrophes
                        segment_contents = segment_contents.replace(
                            "&apos;", "'"
                        ).encode()

                    elif segment._ext == ".ttml2":
                        # Convert ttml2 subtitles to Subrip
                        subrip_contents = ""
                        subtitle_entries = re.findall(
                            r"<p.+</p>", segment_contents.decode()
                        )
                        i = 1
                        for p in subtitle_entries:
                            # begin time
                            begin = (
                                re.search(r'begin="([\d:.]+)"', p)
                                .group(1)
                                .replace(".", ",")
                            )
                            # end time
                            end = (
                                re.search(r'end="([\d:.]+)"', p)
                                .group(1)
                                .replace(".", ",")
                            )
                            # Get the entries content and replace
                            # line break tags with new lines
                            contents = (
                                re.search(r">(.+)</p>", p).group(1).replace("<br/>", "\n")
                            )
                            # Cleanup
                            contents = re.sub(r"<(|/)span>", "", p)
                            contents = contents.replace("&gt;", "")
                            contents = contents.strip()
                            subrip_contents += f"{i}\n{begin} --> {end}\n{contents}\n\n"
                            i += 1
                        segment_contents = subrip_contents.encode()
                        segment_path = segment_path.replace(".ttml2", ".srt")

                    # handle signaling
                    while True:
                        signals = self.check_signal()
                        if signals:
                            # take the first signal
                            signal = signals[0]
                            # if signal is stop, return
                            if signal == PenguinSignals.STOP:
                                return
                            # if signal is pause or nospace, halt execution
                            # until signal is cleared
                            if signal == PenguinSignals.PAUSE:
                                while signal == PenguinSignals.PAUSE:
                                    sleep(0.2)
                        break

                    # Write fragment data to file
                    mkfile(segment_path, segment_contents, False, "wb")

                    thread_vprint(
                        lang["penguin"]["segment_downloaded"] % segment._id,
                        level="verbose",
                        module_name=thread_name,
                        lock=self.thread_lock,
                    )

                    segment._finished = True

                    self.resume_stats["segments_downloaded"].append(segment._id)

                    break

    def check_signal(self) -> int:
        """Check if a signal has been sent to this PenguinDownloader object"""
        return [x for x in ("all", self._thread_id) if x in self._SIGNAL]
