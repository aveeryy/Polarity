from dataclasses import dataclass, field

from polarity.types.base import MediaType
from polarity.types.episode import Episode
from polarity.types.person import Actor, Person
from polarity.types.season import Season


@dataclass
class Series(MediaType):
    title: str
    id: str
    synopsis: str
    genres: list
    year: int
    images: list
    season_count: int
    episode_count: int
    people = []
    seasons: list[Season] = field(default_factory=list)
    extracted = False

    def link_person(self, person: Person) -> None:
        if person not in self.actors:
            self.actors.append(person)

    def link_season(self, season: Season) -> None:
        if season not in self.seasons:
            season._parent = self
            self.seasons.append(season)

    def get_season_by_id(self, season_id: str) -> Season:
        match = [s for s in self.seasons if s.id == season_id]
        if match:
            return match[0]

    def get_all_episodes(self) -> list[Episode]:
        return [e for s in self.seasons for e in s.episodes]
