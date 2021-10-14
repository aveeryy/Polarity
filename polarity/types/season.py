from .base import PolarType
from .episode import Episode
from dataclasses import dataclass, field

@dataclass
class Season(PolarType):
    title: str
    id: str
    number: int
    year: int = 1970
    images: list[str] = field(default_factory=list)
    episode_count: int = 0
    finished: bool = True
    synopsis: str = ''
    episodes = []
    _parent = None

    def link_episode(self, episode: Episode):
        if episode not in self.episodes:
            episode._parent = self
            self.episodes.append(episode)