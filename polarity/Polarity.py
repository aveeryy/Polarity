import datetime
import json
import logging
import os
import platform
import re
import shutil
import sys
import time
import warnings
from copy import deepcopy
from threading import Lock
from typing import Dict, List, Union

import tomli
from tqdm import TqdmWarning

from polarity.config import (
    USAGE,
    change_verbose_level,
    options,
    paths,
)
from polarity.downloader import PenguinDownloader
from polarity.extractor import CONTENT_EXTRACTORS, EXTRACTORS, flags
from polarity.lang import lang, installed_languages
from polarity.types import (
    Content,
    Episode,
    MediaType,
    Movie,
    SearchResult,
    Season,
    Series,
    Thread,
)
from polarity.types.download_log import DownloadLog
from polarity.types.filter import Filter, build_filter
from polarity.types.progressbar import ProgressBar
from polarity.update import check_for_updates, windows_setup
from polarity.utils import FormattedText as FT, get_installation_path
from polarity.utils import (
    dict_merge,
    filename_datetime,
    get_compatible_extractor,
    is_content_id,
    normalize_number,
    parse_content_id,
    sanitize_path,
    send_android_notification,
    set_console_title,
    vprint,
)
from polarity.version import __version__

warnings.filterwarnings("ignore", category=TqdmWarning)


class Polarity:
    def __init__(
        self,
        urls: list,
        opts: dict = None,
        _verbose_level: str = None,
        _logging_level: str = None,
    ) -> None:
        """
        Polarity class


        :param urls: urls/content identifiers if mode is download,
        list of keywords if mode is search
        :param opts: scripting options
        :param _verbose_level: override print verbose lvl
        :param _logging_level: override log verbose lvl
        """

        from polarity import log_filename

        self.urls = urls
        # Load the download log from the default path
        self.__download_log = DownloadLog()
        self.__extract_lock = Lock()
        # List with extracted Episode or Movie objects, for download tasks
        self.download_pool = []
        # List with extracted Series or Movie objects, for metadata tasks
        self.extracted_items = []
        # List with active downloaders
        self._downloaders = []
        self._started = False
        self._finished_extractions = False
        self._start_time = 0
        self._end_time = 0

        # Print versions
        vprint(lang["polarity"]["using_version"] % __version__, level="debug")
        vprint(
            lang["polarity"]["python_version"]
            % (platform.python_version(), platform.platform()),
            level="debug",
        )
        vprint(lang["polarity"]["log_path"] % log_filename, "debug")

        set_console_title(f"Polarity {__version__}")

        # Warn user of unsupported Python versions
        if sys.version_info <= (3, 6):
            vprint(
                lang["polarity"]["unsupported_python"] % platform.python_version(),
                level="warning",
            )

        if opts is not None:
            # Merge user's script options with processed options
            dict_merge(options, opts, overwrite=True, modify=True)

        # for some fucking reason the whole "hooks" key dissapears
        # from the options dictionary so here's (hopefully) a
        # workaround for that
        self.hooks = options["hooks"] if "hooks" in options else {}

        # Scripting only, override the session verbose level,
        # since verbose level is set before options merge.
        if _verbose_level is not None:
            change_verbose_level(_verbose_level, True)
        if _logging_level is not None:
            change_verbose_level(_logging_level, False, True)

    def cleanup(self):
        """
        Executed on a KeyboardInterrupt exception by the __main__ module

        Avoids conflicts by removing locks from downloads
        """
        for downloader in self._downloaders:
            vprint(lang["main"]["unlocking"] % downloader.name, "debug")
            downloader._unlock()

    def delete_session_log(self) -> None:
        """Delete the log created by this instance"""
        try:
            from polarity import log_filename
        except ImportError:
            return
        # avoid "file in use" error on Windows
        for handler in logging.getLogger("polarity").handlers:
            handler.close()
        # remove the log file
        if os.path.exists(log_filename):
            os.remove(log_filename)

    def start(self):
        def create_tasks(name: str, _range: int, _target: object) -> List[Thread]:
            tasks = []
            for i in range(_range):
                t = Thread(
                    f"{name}_Task", i, target=_target, kwargs={"id": i}, daemon=True
                )
                tasks.append(t)
            return tasks

        self._start_time = time.time()

        # Pre-start functions

        if options["list_languages"]:
            print(f"{FT.bold}{lang['polarity']['installed_languages']}{FT.reset}")
            for code, _lang in installed_languages.items():
                print(
                    f"* {lang['polarity']['language_format'] % (_lang['name'], code, _lang['author'])}"
                )
            self.delete_session_log()
            os._exit(0)

        # Windows dependency install
        if options["windows_setup"]:
            windows_setup()

        # Check for updates
        if options["check_for_updates"]:
            update, last_version = check_for_updates()
            if update:
                vprint(
                    lang["polarity"]["update_available"] % last_version,
                    module_name="update",
                )

        if options["dump"]:
            self.dump_information(options["dump"])

        # Actual start-up
        if options["mode"] == "download":
            if not self.urls:
                vprint(lang["polarity"]["deleting_log"], "debug")
                self.delete_session_log()
                # Exit if not urls have been inputted
                print(f"{lang['polarity']['use']}{USAGE}\n")
                print(lang["polarity"]["use_help"])
                os._exit(1)

            if not shutil.which("ffmpeg"):
                raise Exception(lang["polarity"]["except"]["missing_ffmpeg"])

            self.pool = [
                {
                    "url": url,
                    "filters": [],
                    "reserved": False,
                    "extractor": get_compatible_extractor(url),
                }
                for url in set(self.urls)
            ]

            for item in self.pool:
                # check if item's extractor requires login, if yes,
                # ask user for login here, otherwise if more than one url
                # is inputted the email and password prompts would collide one
                # with eachother
                if (
                    flags.ExtractionLoginRequired in item["extractor"][1].FLAGS
                    and not item["extractor"][1]().is_logged_in()
                ):
                    vprint(f"{item['extractor'][0]} requires login")
                    # login into the extractor
                    item["extractor"][1]().login()

            if options["filters"]:
                self.process_filters(filters=options["filters"])

            # create tasks
            tasks = {
                "extraction": create_tasks(
                    "Extraction",
                    options["extractor"]["active_extractions"],
                    self._extract_task,
                ),
                "download": create_tasks(
                    "Download",
                    options["download"]["active_downloads"],
                    self._download_task,
                ),
                "metadata": [],
            }

            # If there are more desired extraction tasks than urls
            # set the number of extraction tasks to the number of urls
            if options["extractor"]["active_extractions"] > len(self.pool):
                options["extractor"]["active_extractions"] = len(self.pool)

            # Start the tasks
            for task_group in tasks.values():
                for task in task_group:
                    task.start()

            # Wait until workers finish
            while True:
                if not [w for w in tasks["extraction"] if w.is_alive()]:
                    if not self._finished_extractions:
                        vprint(lang["polarity"]["finished_extraction"])
                    self._finished_extractions = True
                    if not [w for w in tasks["download"] if w.is_alive()]:
                        break
                time.sleep(0.1)
            self._end_time = time.time()
            vprint(
                lang["polarity"]["all_tasks_finished"]
                % datetime.timedelta(seconds=self._end_time - self._start_time),
                level="debug",
            )

        elif options["mode"] == "search":
            if not self.urls:
                # no search parameters, clear log and exit
                vprint(lang["polarity"]["deleting_log"], "debug")
                self.delete_session_log()
                print(f'{lang["polarity"]["use"]}{lang["polarity"]["search_usage"]}\n')
                print(lang["polarity"]["use_help"])
                os._exit(1)

            search_string = " ".join(self.urls)
            results = self.search(
                search_string,
                options["search"]["results"],
                options["search"]["results_per_extractor"],
                options["search"]["results_per_type"],
            )
            for group, group_results in results.items():
                for result in group_results:
                    name = result.name
                    if (
                        options["search"]["trim_names"] > 0
                        and len(name) > options["search"]["trim_names"]
                    ):
                        name = f"{name[:options['search']['trim_names']]}..."

                    print(
                        options["search"]["result_format"].format(
                            n=name,
                            t=group,
                            i=result.id,
                            I=result.content_id,
                            u=result.url,
                        )
                    )

        elif options["mode"] == "livetv":
            # TODO: add check for urls
            channel = self.get_live_tv_channel(self.urls[0])
            if channel is None:
                vprint(lang["polarity"]["unknown_channel"], level="error")
                return
            print(channel)

        elif options["mode"] == "debug":
            if options["debug_colors"]:

                change_verbose_level("debug")
                # Test for different color printing
                vprint("demo", module_name="demo")
                vprint("demo", "warning", "demo")
                vprint("demo", "error", "demo")
                vprint("demo", "critical", "demo")
                vprint("demo", "debug", "demo")
                ProgressBar(head="demo", desc="progress_bar", total=0)
                ProgressBar(head="demo", desc="progress_bar", total=1)

    @classmethod
    def search(
        self,
        string: str,
        absolute_max: int = -1,
        max_per_extractor: int = -1,
        max_per_type: int = -1,
    ) -> Dict[MediaType, List[SearchResult]]:
        """
        Search for content in compatible extractors
        
        :param string: search term
        :param absolute_max: maximum number of results
        :param max_per_extractor: maximum number of results per extractor
        :param max_per_type: maximum number of results per content type\
        (episode, movie, etc)
        :return: a dict with the content type (MediaType) as a key and\
        a list of SearchResult instances as the value

        To not set a maximum limit on the results, set the parameter's value to -1
        """

        def can_add_to_list(media_type) -> bool:
            """Returns True if item can be added to results list"""
            conditions = (
                # Absolute maximum
                (sum([len(t) for t in results.values()]), absolute_max, False),
                # Maximum per extractor
                (extractor_results, max_per_extractor, True),
                # Maximum per type
                (len(results[media_type]), max_per_type, False),
            )
            for cond in conditions:
                # check if the limit has been surpassed
                if cond[0] >= cond[1] and cond[1] > 0:
                    if cond[2] and cond[0] < 0:
                        # condition value is set to -1, ignore
                        continue
                    return False
            return True

        # Get a list of extractors with search capabilities
        compatible_extractors = [
            e for e in CONTENT_EXTRACTORS.items() if flags.EnableSearch in e[1].FLAGS
        ]
        # Create an empty dictionary for the results
        results = {Series: [], Season: [], Episode: [], Movie: []}

        for _, extractor in compatible_extractors:
            # Current extractor results added to list
            extractor_results = 0
            # Do the search
            search_results = extractor().search(string, max_per_extractor, max_per_type)
            for media_type, _results in search_results.items():
                for result in _results:
                    if can_add_to_list(media_type):
                        # Add item to respective list
                        results[media_type].append(result)
                        extractor_results += 1
        return results

    @classmethod
    def get_live_tv_channel(self, id: str) -> str:
        extractors = {
            n.lower(): e for n, e in EXTRACTORS.items() if flags.EnableLiveTV in e.FLAGS
        }
        parsed_id = parse_content_id(id)
        if parsed_id.extractor not in extractors:
            return
        return extractors[parsed_id.extractor].get_live_tv_stream(parsed_id.id)

    def dump_information(self, info: list) -> None:
        "Dump requested debug information to current directory"
        dump_time = filename_datetime()

        if "options" in info:
            with open(
                f'{paths["log"]}/options_{dump_time}.json', "w", encoding="utf-8"
            ) as f:
                json.dump(options, f, indent=4)
            vprint(
                lang["polarity"]["dumped_to"]
                % (
                    lang["polarity"]["dump_options"],
                    f"{paths['log']}/options{dump_time}.json",
                ),
                level="info",
            )

        # if 'requests' in options['dump']:
        #    vprint('Enabled dumping of HTTP requests', error_level='debug')

    def process_filters(self, filters: str, link=True) -> List[Filter]:
        "Create Filter objects from a string and link them to their respective links"
        filter_list = []
        skip_next_item = False  # If True, skip a item in the loop
        current_index = None  # If None, apply filter to all URLs
        indexed = 0
        url_specifier = r"(global|i(\d)+)"
        filters = re.findall(r'(?:[^\s,"]|"(?:\\.|[^"])*")+', filters)
        vprint(lang["polarity"]["filter_processing"], "debug", "polarity")
        for filter in filters:
            if skip_next_item:
                skip_next_item = False
                continue
            specifier = re.match(url_specifier, filter)
            if specifier:
                if specifier.group(1) == "global":
                    current_index = None
                elif specifier.group(1) != "global":
                    current_index = int(specifier.group(2))
                vprint(
                    lang["polarity"]["changed_index"] % current_index
                    if current_index is not None
                    else "global",
                    level="debug",
                )
            else:
                _index = filters.index(filter, indexed)
                # Create a Filter object with specified parameters
                # and the next iterator, the actual filter
                raw_filter = filters[_index + 1]
                # Remove quotes
                if raw_filter.startswith('"') and raw_filter.endswith('"'):
                    raw_filter = raw_filter[1:-1]
                _filter = build_filter(params=filter, filter=raw_filter)
                filter_list.append(_filter)
                vprint(
                    lang["polarity"]["created_filter"]
                    % (_filter.__class__.__name__, filter, raw_filter),
                    level="debug",
                )
                # Append to respective url's filter list
                if link:
                    if current_index is not None:
                        self.pool[current_index]["filters"].append(_filter)
                    elif current_index is None:
                        # If an index is not specified, or filter is in
                        # global group, append to all url's filter lists
                        for url in self.pool:
                            url["filters"].append(_filter)
                # Avoid creating another Filter object with the filter
                # as the parameter
                skip_next_item = True
                indexed += 2
        return filter_list

    def _execute_hooks(self, name: str, content: dict) -> None:
        if name not in self.hooks:
            return
        for hook in self.hooks[name]:
            hook(content)

    def _extract_task(self, id: int) -> None:
        def take_item() -> Union[dict, None]:
            with self.__extract_lock:
                available = [i for i in self.pool if not i["reserved"]]
                if not available:
                    return
                item = available[0]
                self.pool[self.pool.index(item)]["reserved"] = True
            return item

        while True:
            item = take_item()
            if item is None:
                break
            _extractor = get_compatible_extractor(item["url"])
            if _extractor is None:
                vprint(
                    lang["dl"]["no_extractor"]
                    % (
                        lang["dl"]["url"]
                        if not is_content_id(item["url"])
                        else lang["dl"]["content_id"],
                        item["url"],
                    )
                )
                continue

            name, extractor = _extractor
            self._execute_hooks(
                "started_extraction", {"extractor": name, "name": item["url"]}
            )
            extractor_object = extractor(item["url"], item["filters"], _thread_id=id)
            extracted_info = extractor_object.extract()
            self.extracted_items.append(extracted_info)

            while True:
                contents = extracted_info.get_all_content(pop=True)
                if not contents and extracted_info._extracted:
                    # No more content to add to download list
                    # and extractor finish, end loop
                    break
                for content in contents:
                    file_path = self._format_filename(content)
                    content.output = file_path
                    self.download_pool.append(content)

            self._execute_hooks(
                "finished_extraction", {"extractor": name, "name": item["url"]}
            )

    def _download_task(self, id: int) -> None:
        while True:
            if not self.download_pool and self._finished_extractions:
                break
            elif not self.download_pool:
                time.sleep(1)
                continue
            # Take an item from the download pool
            item = self.download_pool.pop(0)
            if item.skip_download is not None:
                vprint(
                    lang["dl"]["cannot_download_content"]
                    % (
                        lang["types"][type(item).__name__.lower()],
                        item.short_name,
                        item.skip_download,
                    ),
                    level="warning",
                )
                continue
            elif (
                self.__download_log.in_log(item.content_id)
                and not options["download"]["redownload"]
            ):
                vprint(lang["dl"]["no_redownload"] % item.short_name, level="warning")
                continue

            vprint(
                lang["dl"]["downloading_content"]
                % (lang["types"][type(item).__name__.lower()], item.short_name)
            )

            # Set the downloader to Penguin
            # TODO: external downloader support
            _downloader = PenguinDownloader
            downloader = _downloader(item, _options={"hooks": self.hooks}, _thread_id=id)
            self._downloaders.append(downloader)
            downloader.start()
            # wait until downloader has finished
            while downloader.is_alive():
                time.sleep(0.1)
            del self._downloaders[self._downloaders.index(downloader)]

            if downloader.success:
                vprint(
                    lang["dl"]["download_successful"]
                    % (lang["types"][item.__class__.__name__.lower()], item.short_name)
                )
                send_android_notification(
                    "Polarity",
                    lang["dl"]["download_successful"]
                    % (lang["types"][item.__class__.__name__.lower()], item.short_name),
                    id=item.short_name,
                    action=f"'termux-share \"{item.output}\"'",
                )
                # Download finished, add identifier to download log
                self.__download_log.add(item.content_id)

    @staticmethod
    def _format_filename(content: Union[Episode, Movie, Content]) -> str:
        """
        Create an output path for an Content object using it's
        metadata

        :param content: an instance of a Content class
        :return: formatted path based on configuration
        """

        fields = {
            "base": "",
            "title": "",
            "id": "",
            "number": 0,
            "number_0": "00",
            "year": "",
            "extractor": "",
            "season_title": "",
            "season_id": "",
            "season_number": 0,
            "season_number_0": "00",
            "season_year": "",
            "series_title": "",
            "series_id": "",
            "series_year": "",
            "ext": "mkv",
        }

        # create a copy of the empty fields
        empty_fields = deepcopy(fields)

        if type(content) in (Episode, Content):
            # merge Episode fields
            if type(content) is Episode:
                path = options["download"]["series_directory"]
                base = options["download"]["episode_format"]
                dict_merge(
                    fields,
                    {
                        "number": content.number,
                        "number_0": normalize_number(content.number),
                    },
                    overwrite=True,
                )

            elif type(content) is Content:
                path = options["download"]["generic_directory"]
                base = options["download"]["generic_format"]

            # merge Episode/Content common fields
            dict_merge(
                fields,
                {
                    "extractor": content.extractor,
                    "title": content.title.replace("/", "-"),
                    "id": content.id,
                    "year": content.date.year,
                    "ext": "mkv",
                },
                overwrite=True,
            )

            if hasattr(content, "_series") and content._series is not None:
                dict_merge(
                    fields,
                    {
                        "series_title": content._series.title.replace("/", "-"),
                        "series_id": content._series.id,
                        "series_year": content._series.date.year,
                    },
                    overwrite=True,
                )

                if hasattr(content, "_season") and content._season is not None:
                    dict_merge(
                        fields,
                        {
                            "season_title": content._season.title.replace("/", "-"),
                            "season_id": content._season.id,
                            "season_number": content._season.number,
                            "season_number_0": normalize_number(content._season.number),
                            "season_year": content._season.date.year,
                        },
                        overwrite=True,
                    )

        elif type(content) == Movie:
            path = options["download"]["movies_directory"]
            base = options["download"]["movie_format"]

            dict_merge(
                fields,
                {
                    "extractor": content.extractor,
                    "title": content.title.replace("/", "-"),
                    "id": content.id,
                    "year": content.date.year,
                    "ext": "mkv",
                },
                overwrite=True,
            )

        # TODO: add check for invalid fields

        # fill the fields
        filled = base.format(**fields).split("/")
        empty = base.format(**empty_fields).split("/")
        # remove empty segments of the path
        removed = [part for n, part in enumerate(filled) if empty[n] != part]
        # join the download path and the built path
        final_path = "/".join(removed)
        # small workaround if content download path is not present
        # in output path, adds current working path
        if r"{base}" in base:
            final_path = os.path.join(path, final_path)
        else:
            final_path = os.path.join(os.getcwd(), final_path)

        # finally return the sanitized path
        return sanitize_path(final_path)
