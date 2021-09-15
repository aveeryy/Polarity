from .base import PolarType
from .episode import Episode
class Season(PolarType):
    def __init__(self) -> None:
        self.title = None
        self.id = None
        self.synopsis = None
        self.number = 0
        self.year = 1970
        self.images = []
        self.total_episodes = 0
        self.available_episodes = 0
        self.finished = False
        self.episodes = []
        self._parent = None

    def link_episode(self, episode=Episode):
        if episode not in self.episodes:
            episode._parent = self
            self.episodes.append(episode)