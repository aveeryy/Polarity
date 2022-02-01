import re

from typing import List

from polarity.types import str_to_type, stringified_types


class Filter:
    """
    ### Content filters:
    available types:
    - number: filter by season or/and episode number
    - match: filter by (not) matching title, allows regular expressions
    """

    def __init__(self, filter: str) -> None:
        self._filter = filter
        self._properties = {}

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.raw_filter})"

    @property
    def raw_filter(self):
        return self._filter

    @property
    def properties(self):
        return self._properties

    def check(self, object):
        "Check if item passes the filter"
        return self._check(object)


class NumberFilter(Filter):

    regex = {
        "single": r"(?P<type>S|E|s|e)(?P<num>\d+)",
        "multi": r"(?:S|s)(?P<season>\d+)(?:E|e)(?P<episode>\d+)",
        "range": r"(?P<type>S|E|s|e)(?P<start>\d+)(?:-|/)(?P<end>\d+)",
    }

    def __init__(self, filter: str) -> None:
        super().__init__(filter)

        self._properties = {
            "single": None,
            "multi": all(
                (
                    # Check for capitalized letters in filter
                    any(val in filter for val in ("S", "s")),
                    # Check for non-capitalized letters in filter
                    any(val in filter for val in ("E", "e")),
                )
            ),
            "range": any(val in filter for val in ("-", "/")),
        }
        self._properties["single"] = (
            not self._properties["multi"] and not self._properties["range"]
        )

        self.__seasons = []
        self.__episodes = []
        self.__parse_filter_obj()

    @property
    def seasons(self) -> List[int]:
        return self.__seasons

    @property
    def episodes(self) -> List[int]:
        return self.__episodes

    def __parse_filter_obj(self):
        "Parses a filter string and puts season/episode numbers in their respective lists"

        if self.properties["single"]:
            # Single numbers, examples: S01, S6, E04, E12
            match = re.match(self.regex["single"], self._filter)
            filter_list = (
                self.__seasons if match.group("type") in ("S", "s") else self.__episodes
            )
            filter_list.append(int(match.group("num")))

        elif self.properties["multi"]:
            # Specifies episode of a season, example: S01E05, S07E12, S4E3
            match = re.match(self.regex["multi"], self._filter)
            self.__seasons.append(int(match.group("season")))
            self.__episodes.append(int(match.group("episode")))

        elif self.properties["range"]:
            # Range of seasons/episodes, examples: S01-12, S6-9, E12-45, E2-3
            match = re.match(self.regex["range"], self._filter)
            filter_list = (
                self.__seasons if match.group("type") in ("S", "s") else self.__episodes
            )
            # Create a list of a range, indented for readability
            filter_list.extend(
                list(range(int(match.group("start")), int(match.group("end")) + 1))
            )

    def _check(self, obj):
        if self.properties["multi"]:
            return (
                obj.season_number in self.__seasons
                and obj.episode_number in self.__episodes
            )
        return (
            obj.season_number in self.__seasons or obj.episode_number in self.__episodes
        )


class MatchFilter(Filter):
    def __init__(self, filter: str, full=False, not_match=False, absolute=False) -> None:
        if full:
            filter = f"^{filter}$"
        filter = re.compile(pattern=filter)
        super().__init__(filter)
        self.__absolute = absolute
        self.__not_match = not_match

    @property
    def absolute(self):
        return self.__absolute

    @property
    def not_match(self):
        return self.__not_match

    def _check(self, object):
        match = re.search(self._filter, object.title)
        if self.__not_match:
            return not match
        return bool(match)


class TypeFilter(Filter):
    def __init__(self, filter: str) -> None:
        raise NotImplementedError
        if filter.lower() not in stringified_types:
            raise Exception
        self.__type = str_to_type(filter)
        super().__init__(filter)

    def _check(self, object) -> bool:
        return type(object) == self.__type


def build_filter(params: str, filter: str) -> None:
    """
    Create a filter based on passed parameters and filter string

    Examples of a parameter string
    - match  / Just the Filter type, no parameters
    - match_regex  / `match` Filter type with `regex` parameter
    - match_regex_full  / `match` Filter type with `regex` and `full` parameters
    """

    types = {
        "number": {"obj": NumberFilter, "params": {}},
        "match": {
            "obj": MatchFilter,
            "params": {
                "regex": False,
                "full": False,
                "not_match": False,
                "absolute": False,
            },
        },
        "notmatch": {
            "obj": MatchFilter,
            "params": {
                "regex": False,
                "full": False,
                "not_match": True,
                "absolute": False,
            },
        },
    }
    unparsed = params.split("_")
    if len(unparsed) >= 1:
        raw_parameters = unparsed[1:]
        # Create a dictionary based on "parameter: True" entries
        parameters = {k: True for k in raw_parameters}
    else:
        parameters = {}
    filter_type = unparsed[0]
    filter_object = types[filter_type]["obj"]
    defaults = types[filter_type]["params"]
    # Create the final Filter object
    _filter = filter_object(
        filter=filter,
        # Merge the filter defaults with passed parameters
        **{**defaults, **parameters},
    )

    return (_filter, filter_object)
