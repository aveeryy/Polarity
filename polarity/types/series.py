from .base import PolarType
from .person import Person, Actor
from .season import Season
from dataclasses import dataclass

@dataclass
class Series(PolarType):
    title: str
    id: str
    synopsis: str
    genres: list
    year: int
    images: list
    season_count: int
    episode_count: int
    people = []
    seasons = []

    def link_person(self, person: Person) -> None:
        if person not in self.actors:
            self.actors.append(person)

    def link_season(self, season: Season) -> None:
        if season not in self.seasons:
            season._parent = self
            self.seasons.append(season)

    def get_all_episodes(self) -> list:
        return [e for s in self.seasons for e in s.episodes]