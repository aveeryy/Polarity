from polarity.types.base import MediaType, MetaMediaType
from .episode import Episode
from dataclasses import dataclass, field


@dataclass
class Season(MediaType, metaclass=MetaMediaType):
    title: str = None
    id: str = None
    number: int = None
    year: int = 1970
    images: list[str] = field(default_factory=list)
    episode_count: int = 0
    finished: bool = True
    synopsis: str = ""
    episodes: list[Episode] = field(init=False)
    _series = None
    _partial = True

    def __post_init__(self):
        self.episodes = []
        self.__episodes = []

    def link_episode(self, episode: Episode):
        if episode not in self.episodes:
            episode._season = self
            episode._series = self._series
            self.episodes.append(episode)
            self.__episodes.append(episode)

    @property
    def all_episodes(self) -> list[Episode]:
        """Returns all episodes, even if popped by `get_all_episodes`"""
        return self.__episodes
