# flake8: noqa

# Integrated language
# Uses very simple english words, and does not require installation
# so pretty much failure-proof, for example, if language files have not been
# updated it takes missing strings from here.
internal_lang = {
    # Language metadata
    "name": "Polarity Internal language",
    "code": "internal",
    "author": "aveeryy",
    "main": {"exit_msg": "exiting...", "unlocking": "unlocking %s's download"},
    # Argument string group
    "args": {
        "added_arg": 'added: arg "%s" from %s',
        # Argument groups string sub-group
        "groups": {
            "general": "general options",
            "download": "download options",
            "extractor": "%s options",
            "debug": "debug options",
            "search": "search options",
        },
        # Argument help string sub-group
        "help": {
            "accounts_dir": "custom directory for account files",
            "binaries_dir": "custom directory with ffmpeg binaries",
            "config_file": "custom configuration file path",
            "download_dir_series": "download dir for tv series",
            "download_dir_movies": "download dir for movies",
            "dump": "dump information to a file",
            "email": "%s account email",
            "exit_after_dump": "exit after dumping information",
            "extended_help": "shows help with argument options",
            "filters": "extraction and download filters",
            "format_episode": "formatting for episodes' filenames",
            "format_movie": "formatting for movies' filenames",
            "format_season": "formatting for seasons' directories",
            "format_series": "formatting for tv series' directories",
            "format_search": "formatting for search results",
            "help": "shows help",
            "install_languages": "install specified languages",
            "installed_languages": "list installed languages",
            "language": "load specified language",
            "language_dir": "custom directory for language files",
            "log_dir": "custom directory for logs",
            "log_file": "custom download log file path",
            "max_results": "maximum number of results",
            "max_results_per_extractor": "maximum number of results per extractor",
            "max_results_per_type": "maximum number of results per media type",
            # TODO: better 'mode' string
            "mode": "execution mode",
            "pass": "%s account password",
            "redownload": "allow episode redownload",
            "remove_chars": "remove invalid windows characters instead of replacing",
            "resolution": "preferred resolution",
            "results_trim": "trim search results' names",
            "temp_dir": "custom directory for temporary files",
            "update": "update to latest release",
            "update_check": "check for updates on startup",
            "update_git": "update to latest git commit",
            "update_languages": "update installed language files",
            "url": "input urls",
            "verbose": "verbose level",
            "verbose_log": "verbose level for logging",
        },
    },
    "polarity": {
        "all_tasks_finished": "finished everything, took: %s",
        "available_languages": "available languages:",
        "changed_index": "changed index: %s",
        "config_path": "config path: %s",
        "created_filter": 'created: %s object with params "%s" and filter "%s"',
        "deleting_log": "nothing to do, deleting log",
        "dump_options": "options",
        "dumped_to": "dumped %s to: %s",
        "filter_processing": "started: filter processing",
        "finished_download": "finished: download tasks",
        "finished_extraction": "finished: extraction tasks",
        "installed_languages": "installed languages:",
        "language_format": "%s [%s] by %s",
        "log_path": "writing log to: %s",
        "not_a_content_id": '"%s" is not a content identifier',
        "no_space_left": "no space left on device, exiting...",
        "python_version": "Python %s | %s",
        "requesting": "requesting %s",
        "search_no_results": "no results from search %s",
        "search_term": "term: ",
        "search_usage": "polarity --mode search [OPTIONS] <search parameters>",
        "unknown_channel": "unknown channel",
        "unsupported_python": "unsupported python version (%s), update to python 3.7 or higher",
        "update_available": "version %s available",
        "usage": "polarity [OPTIONS] <url(s)>",
        "use_help": "use --help to display all options",
        "use": "usage: ",
        "using_version": "Polarity %s",
        "except": {
            "invalid_http_method": "invalid method: %s",
            "missing_ffmpeg": "ffmpeg is not installed or not in PATH",
            "verbose_error": "invalid verbose level: %s",
            "verbose_log_error": "invalid verbose log level: %s",
        },
    },
    "dl": {
        "cannot_download_content": '%s "%s" can\'t be downloaded: %s',
        "content_id": "content id",
        "download_successful": 'downloaded: %s "%s"',
        "downloading_content": 'downloading: %s "%s"',
        "no_extractor": 'skipping: %s "%s". no extractor',
        "no_redownload": "skipping: %s already downloaded",
        "url": "url",
    },
    "penguin": {
        "assisting": "assisting: thread %s with %s",
        "current_pool": "current pool: %s",
        "doing_binary_concat": "binary concat: track %s of %s",
        "doing_decryption": 'decrypting: track %s of %s with key "%s"',
        "download_locked": 'can\'t download "%s", locked by another downloader',
        "debug_already_downloaded": "skipping segment: %s",
        "debug_time_download": "segment download took: %s",
        "debug_time_remux": "remux took: %s",
        "ffmpeg_remux_failed": "ffmpeg process crashed, aborting, please create a GitHub issue with the following file attached: %s",
        "incompatible_stream": "incompatible stream: %s",
        "key_download": "downloading: key of segment %s",
        # Output file
        "output_file_broken": "failed to load output data file, recreating",
        # Resume file
        "processing_stream": "processing stream: %s",
        "resume_file_backup_broken": "failed to load backup of resume data, recreating",
        "resume_file_broken": "failed to load resume data file, using backup",
        "resume_file_recreation": "recreating: resume data",
        "resuming": "resuming: %s...",
        "segment_downloaded": "downloaded: segment %s",
        "segment_retry": "failed: segment %s download, retrying (%s/%s)...",
        "segment_skip": "skipping: segment %s",
        "segment_start": "start: download of segment %s",
        "stream_protocol": "using: protocol %s for stream %s",
        "thread_started": 'start: downloader "%s"',
        "threads_started": "start: %d download threads",
        "args": {
            "keep_logs": "keep download logs along the final file",
            "tag_output": "add the polarity version to the final file",
            "threads": "number of threads per download",
        },
        "except": {"download_fail": "failed to download segment %s: %s"},
        "protocols": {
            "getting_playlist": "parsing: playlist",
            "getting_stream": "parsing: streams",
            "multiple_video_bitrates": "multiple stream with same resolution detected",
            "picking_best_stream_0": "picking: video stream with highest resolution",
            "picking_best_stream_1": "picking: video stream with highest bitrate",
            "picking_best_stream_2": "picking: audio stream",
            "selected_stream": "stream: %s",
        },
    },
    "extractor": {
        "base": {
            "check_failed": "failed: check for feature \033[1m%s\033[0m, conditions are false: %s",
            "email_prompt": "email/username: ",
            "password_prompt": "password: ",
            "using_filters": "using filters, total count will be inaccurate",
            "except": {
                "argument_variable_empty": "variable argument is empty",
                "failed_load_cookiejar": "failed to load cookiejar: %s",
                "no_cookiejar": "extractor has no cookiejar",
            },
        },
        "check": {
            "features": {
                "base": "base_functionality",
                "login": "login",
                "search": "search",
                "livetv": "live_tv",
            },
            "invalid_extractor": "extractor %s is invalid",
        },
        "filter_check_fail": "didn't pass filter check",
        "generic_error": "error, error msg: ",
        "get_all_seasons": "getting info: seasons",
        "get_media_info": 'getting info: %s "%s" (%s)',
        "login_expired": "login expired, cleaning cookiejar",
        "login_failure": "failed to login, error code: %s",
        "login_loggedas": "logged in as: %s",
        "login_success": "login successful",
        "search_no_results": "no results: category %s with term %s",
        "skip_dl_premium": "premium content, or not in your region",
        "waiting_for_login": "waiting for login",
        "except": {
            "argument_missing": "%s argument is required",
            "cannot_identify_url": "failed to identify URL",
            "no_id": "no id inputted",
            "no_url": "no url inputted",
        },
    },
    "types": {
        "series": "series",
        "season": "season",
        "episode": "episode",
        "movie": "movie",
        "content": "content",
        "contentcontainer": "content container",
        "alt": {
            "series": "series",
            "season": "season",
            "episode": "episode",
            "movie": "movie",
            "content": "content",
            "contentcontainer": "content container",
        },
    },
    "update": {
        "downloading_git": "updating from git repo's branch %s",
        "downloading_release": "updating to latest release",
        "downloading_native": "downloading latest native",
        "new_release": "new release (%s) available",
        "except": {"unsupported_native": "native binary update is not supported yet"},
    },
    "atresplayer": {
        "no_content_in_season": "no episodes in %s (%s)",
        "no_seasons": "content does not have seasons",
        "except": {"invalid_codec": "invalid codec"},
        "args": {"codec": "codec preferance"},
    },
    "crunchyroll": {
        "bearer_fetch": "fetching: bearer token",
        "bearer_fetch_fail": "failed: bearer token fetch",
        "cms_fetch": "fetching: cms policies",
        "cms_fetch_success": "success: cms policies fetch",
        "cms_fetch_fail": "failed: cms policies fetch",
        "unwanted_season": 'skip: season "%s", unwanted dub',
        "using_method": 'login method "%s"',
        "args": {
            "subs": "subtitle languages",
            "dubs": "dub languages",
            "meta": "metadata language",
            "hard": "fetch a hardsubbed version",
        },
    },
    "pokemontv": {
        "get_channel_info": "getting info: channels",
        "get_region_info": "getting info: region",
    },
    "limelight": {
        "available_formats": "available formats: %s",
        "set_wanted_format": "set stream with format %s as wanted",
        "args": {"format": "preferred stream format"},
        "except": {
            "invalid_id": "invalid format identifier: %s",
            "unsupported_rtmp": "rtmp streams are unsupported",
        },
    },
}
