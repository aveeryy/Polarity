from .base import PolarType

from .actor import Actor
from .season import Season

class Series(PolarType):
    def __init__(self) -> None:
        self.title = None
        self.id = None
        self.synopsis = None
        self.actors = []
        self.genres = []
        self.year = 1970
        self.images = []
        self.total_seasons = 0
        self.total_episodes = 0
        self.available_episodes = 0
        self.seasons = []

    def __str__(self) -> str:
        return self.title

    def link_actor(self, actor=Actor) -> None:
        if actor not in self.actors:
            self.actors.append(actor)

    def link_season(self, season=Season) -> None:
        if season not in self.seasons:
            season._parent = self
            self.seasons.append(season)

    def get_all_episodes(self) -> list:
        return [e for s in self.seasons for e in s.episodes]