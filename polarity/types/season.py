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
    synopsis: str = ''
    episodes: list[Episode] = field(default_factory=list)
    _partial = True  # Partial until proven full
    _unwanted = False
    _parent = None

    def link_episode(self, episode: Episode):
        if episode not in self.episodes:
            episode._parent = self
            self.episodes.append(episode)
