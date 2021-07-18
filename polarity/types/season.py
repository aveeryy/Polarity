from polarity.types import Episode
class Season:
    def __init__(self) -> None:
        self.title = None
        self.id = None
        self.synopsis = None
        self.number = 0
        self.total_episodes = 0
        self.available_episodes = 0
        self.episodes = []
        self._parent = None

    def link_episode(self, episode=Episode):
        if not episode in self.episodes:
            episode._parent = self
            self.episodes.append(episode)