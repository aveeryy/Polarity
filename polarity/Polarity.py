import json
import logging
import os
import platform
import re
import shutil
import sys
import time
import warnings
from threading import Lock
from typing import Union, List, Tuple, Dict
import tomli

from tqdm import TqdmWarning

from polarity.config import (
    USAGE,
    change_verbose_level,
    get_installed_languages,
    lang,
    options,
    paths,
)
from polarity.downloader import PenguinDownloader
from polarity.extractor import EXTRACTORS, flags
from polarity.types import (
    Episode,
    Movie,
    SearchResult,
    Season,
    Series,
    Thread,
)
from polarity.types.base import MediaType
from polarity.types.filter import Filter, build_filter
from polarity.types.progressbar import ProgressBar
from polarity.types.download_log import DownloadLog
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
from polarity.update import (
    check_for_updates,
    language_install,
    windows_setup,
)
from polarity.version import __version__

from polarity.utils import FormattedText as FT


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
        Polarity object


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

        self.status = {"pool": urls, "extraction": {"finished": False, "tasks": []}}

        if opts is not None:
            # Merge user's script options with processed options
            dict_merge(options, opts, overwrite=True)
        # Scripting only, override the session verbose level,
        # since verbose level is set before options merge.
        if _verbose_level is not None:
            change_verbose_level(_verbose_level, True)
        if _logging_level is not None:
            change_verbose_level(_logging_level, False, True)

    def delete_session_log(self) -> None:
        try:
            from polarity import log_filename
        except ImportError:
            return

        for handler in logging.getLogger("polarity").handlers:
            handler.close()

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

        # Pre-start functions

        from polarity import log_filename

        # Language installation / update
        # First update old languages
        if options["update_languages"] or options["auto_update_languages"]:
            language_install(get_installed_languages())
        # Then, install new languages
        if options["install_languages"]:
            language_install(options["install_languages"])

        if options["installed_languages"]:
            installed = get_installed_languages()
            if not installed:
                # since no languages are installed there's no need to
                # load this string from lang
                vprint("no languages installed", "error")
                self.delete_session_log()
                os._exit(1)
            print(f"{FT.bold}{lang['polarity']['installed_languages']}{FT.reset}")
            for _lang in get_installed_languages():
                with open(f'{paths["lang"]}{_lang}.toml', "rb") as lf:
                    loaded = tomli.load(lf)
                    name = f"{FT.bold}{loaded['name']}{FT.reset}"
                    print(
                        f"* {lang['polarity']['language_format'] % (name, loaded['code'], loaded['author'],)}"
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
                for url in self.urls
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
                    if not self.status["extraction"]["finished"]:
                        vprint(lang["polarity"]["finished_extraction"])
                    self.status["extraction"]["finished"] = True
                    if not [w for w in tasks["download"] if w.is_alive()]:
                        break
                time.sleep(0.1)
            vprint(lang["polarity"]["all_tasks_finished"])

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
        """Search for content in compatible extractors"""

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
                if cond[0] >= cond[1] and cond[1] > 0:
                    if cond[2] and cond[0] < 0:
                        continue
                    return False
            return True

        # Get a list of extractors with search capabilities
        compatible_extractors = [
            e for e in EXTRACTORS.items() if flags.EnableSearch in e[1].FLAGS
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
        vprint("Starting filter processing", "debug", "polarity")
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
                _filter, filter_type = build_filter(params=filter, filter=raw_filter)
                filter_list.append(_filter)
                vprint(
                    lang["polarity"]["created_filter"]
                    % (filter_type.__name__, filter, raw_filter),
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

    def execute_hooks(self, name: str, content: dict) -> None:
        if "hooks" not in options:
            return
        if name not in options["hooks"]:
            return
        for hook in options["hooks"][name]:
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
            self.execute_hooks(
                "started_extraction", {"extractor": name, "name": item["url"]}
            )
            extractor_object = extractor(item["url"], item["filters"], _stack_id=id)
            extracted_info = extractor_object.extract()
            self.extracted_items.append(extracted_info)

            if type(extracted_info) is Series:
                while True:
                    episodes = extracted_info.get_all_episodes(pop=True)
                    if not episodes and extracted_info._extracted:
                        # No more episodes to add to download list
                        # and extractor finish, end loop
                        break
                    for episode in episodes:
                        if type(episode) is Episode:
                            media = (extracted_info, episode._season, episode)
                        elif type(episode) is Movie:
                            media = Episode
                        media_object = self._format_filenames(media)
                        self.download_pool.append(media_object)

            elif type(extracted_info) is Movie:
                while not extracted_info._extracted:
                    time.sleep(0.1)
                media_object = self._format_filenames(extracted_info)

                # name = f"{paths['log']}/{item['url'].replace('/', '_')}-{filename_datetime()}.log"

                # with open(name, "w") as log:
                #     log.write(extractor_object.logs)

                self.download_pool.append(media_object)
            self.execute_hooks(
                "finished_extraction", {"extractor": name, "name": item["url"]}
            )

    def _download_task(self, id: int) -> None:
        while True:
            if not self.download_pool and self.status["extraction"]["finished"]:
                break
            elif not self.download_pool:
                time.sleep(1)
                continue
            # Take an item from the download pool
            item = self.download_pool.pop(0)
            if (
                item.skip_download is not None
                and item.skip_download != lang["extractor"]["filter_check_fail"]
            ):
                vprint(
                    lang["dl"]["cannot_download_content"]
                    % (type(item).__name__, item.short_name, item.skip_download),
                    level="warning",
                )
                continue
            elif (
                self.__download_log.in_log(item.content_id)
                and not options["download"]["redownload"]
            ):
                vprint(lang["dl"]["no_redownload"] % item.short_name, level="warning")
                continue

            vprint(lang["dl"]["downloading_content"] % (item.short_name, item.title))

            # Set the downloader to Penguin
            # TODO: external downloader support
            _downloader = PenguinDownloader
            downloader = _downloader(item=item, _stack_id=id)
            downloader.start()

            while downloader.is_alive():
                time.sleep(0.1)

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
                    # TODO: rework when music support is finished
                    action=f"'termux-share \"{item.output}{options['download']['video_extension']}\"'",
                )
                # Download finished, add identifier to download log
                self.__download_log.add(item.content_id)

    @staticmethod
    def _format_filenames(
        media_obj: Union[Tuple[Series, Season, Episode], Movie],
    ) -> Union[Episode, Movie, Tuple[str]]:
        """
        Create an output path out of an MediaType object metadata
        :param media_obj: a tuple with a series, season and episode object, in that order,
        or a movie object
        """
        if type(media_obj) is tuple:
            series_dir = options["download"]["series_format"].format(
                # Extractor's name
                W=media_obj[0]._extractor,
                # Series' title
                S=media_obj[0].title,
                # Series' identifier
                i=media_obj[0].id,
                # Series' year
                y=media_obj[0].year,
            )
            season_dir = options["download"]["season_format"].format(
                # Extractor's name
                W=media_obj[0]._extractor,
                # Series' title
                S=media_obj[0].title,
                # Season's title
                s=media_obj[1].title,
                # Season's identifier
                i=media_obj[1].id,
                # Season's number with trailing 0 if < 10
                sn=normalize_number(media_obj[1].number),
                # Season's number
                Sn=media_obj[1].number,
            )
            output_filename = (
                options["download"]["episode_format"]
                .format(
                    # Extractor's name
                    W=media_obj[0]._extractor,
                    # Series' title
                    S=media_obj[0].title,
                    # Season's title
                    s=media_obj[1].title,
                    # Episode's title
                    E=media_obj[2].title,
                    # Episode's identifier
                    i=media_obj[2].id,
                    # Season's number with trailing 0 if < 10
                    sn=normalize_number(media_obj[1].number),
                    # Season's number
                    Sn=media_obj[1].number,
                    # Episode's number with trailing 0 if < 10
                    en=normalize_number(media_obj[2].number),
                    # Episode's number
                    En=media_obj[2].number,
                )
                .replace("/", "-")
            )
            output_path = os.path.join(
                options["download"]["series_directory"],
                series_dir,
                season_dir,
                output_filename,
            )
            media_obj[2].output = sanitize_path(output_path)
            return media_obj[2]
        if type(media_obj) is Movie:
            output_filename = (
                options["download"]["movie_format"]
                .format(
                    # Extractor's name
                    W=media_obj._extractor,
                    # Movie's title
                    E=media_obj.title,
                    # Movie's identifier
                    i=media_obj.id,
                    # Movie's year
                    Y=media_obj.year,
                )
                .replace("/", "-")
            )
            output_path = os.path.join(
                options["download"]["movie_directory"], output_filename
            )
            media_obj.output = sanitize_path(output_path)
            return media_obj
