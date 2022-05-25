from polarity.utils import get_config_path, get_home_path

# Base path for configuration files
__main_path = get_config_path()
# Default base path for downloads
__download_path = f"{get_home_path()}/Polarity Downloads"

# Default config values
config = {
    # Verbosity level
    # Does not affect logs
    "verbose": "info",
    # Log verbosity level
    # This must be debug (or higher) to report an issue
    "verbose_logs": "debug",
    # Language file to use
    # Leave empty to use internal language
    # 'internal' also works
    "language": "internal",
    # Check for updates on start-up
    # This does not automatically update Polarity
    "check_for_updates": False,
    # Download options
    "download": {
        # Maximum active downloads
        "active_downloads": 3,
        # Output directory for series
        "series_directory": f"{__download_path}/Series".replace("\\", "/"),
        # Output directory for movies
        "movies_directory": f"{__download_path}/Movies".replace("\\", "/"),
        # Output directory for generic content
        "generic_directory": f"{__download_path}".replace("\\", "/"),
        # Formatting for episodes
        "episode_format": """
        {base}{extractor}/{series_title} [{series_id}]/\
        Season {season_number} [{season_id}]/\
        {series_title} S{season_number_0}E{number_0} - {title}.{ext}
        """.replace(
            "\n", ""  # remove newlines
        ).replace(
            " " * 8, ""  # remove indentation
        ),
        # Filename formatting for movies
        # Default format: Movie title (Year)
        "movie_format": "{base}{extractor}/{title} ({year}).{ext}",
        # Filename formatting for generic content
        "generic_format": "{base}{extractor}/{title} [{id}].{ext}",
        # Desired video resolution, number must be height
        # If resolution is not available, gets the closest value
        "resolution": 4320,
        # Allow downloading previously downloaded episodes
        "redownload": False,
        "penguin": {
            "attempts": 3,
            "threads": 5,
            # Add a metadata entry with the Polarity version
            "tag_output": False,
            # Copy download logs to final download path
            "keep_logs": False,
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
        },
    },
    # Extractor options
    "extractor": {
        # Number of extraction threads, one per URL
        "active_extractions": 5,
        # Extractor's defaults
        "atresplayer": {
            # Prefer HEVC codec if available
            "use_hevc": True,
        },
        "crunchyroll": {
            # Subtitle languages to download
            # Possible values:
            # all, none, en-US, es-ES, es-LA, fr-FR, pt-BR, de-DE, it-IT,
            # ar-ME, ru-RU and tr-TR
            "sub_language": ["all"],
            # Dub languages to extract
            # Possible values:
            # all, ja-JP, en-US, es-LA, fr-FR, pt-BR, de-DE, it-IT and ru-RU
            "dub_language": ["all"],
            # Metadata language
            # Possible values:
            # auto, en-US, es-ES, es-LA, fr-FR, pt-BR, de-DE, it-IT,
            # ar-ME and ru-RU
            "meta_language": "auto",
            # Hardsubbed version to download
            # Possible values:
            # none, en-US, es-ES, es-LA, fr-FR, pt-BR, de-DE, it-IT,
            # ar-ME, ru-RU and tr-TR
            "hardsub_language": "none",
        },
        "limelight": {
            "preferred_format": "http",
        },
    },
    "search": {
        # Absolute maximum for results
        "results": 50,
        # Maximum results per extractor
        "results_per_extractor": 20,
        # Maximum results per
        "results_per_type": 20,
        # Trim results' name length to this value
        # -1 or 0 to disable
        "trim_names": -1,
        # Format for results
        # Default format: Title (Polarity content ID [extractor/type-id])
        # Default example: Pokémon (atresplayer/series-000000)
        # Available format codes:
        # https://github.com/aveeryy/Polarity/tree/main/polarity/docs/format.md
        "result_format": "{n} ({I})",
    },
}

# Default paths
paths = {
    k: __main_path + v
    for k, v in {
        "account": "Accounts/",
        "bin": "Binaries/",
        "cfg": "config.toml",
        "dl_log": "download.log",
        "dump": "Dumps/",
        "log": "Logs/",
        "tmp": "Temp/",
    }.items()
}

VALID_VERBOSE_LEVELS = [
    "quiet",
    "critical",
    "error",
    "warning",
    "info",
    "debug",
    "verbose",
]
