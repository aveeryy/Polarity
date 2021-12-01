from dataclasses import dataclass, field, asdict

from polarity.types.base import MediaType, MetaMediaType, MetaMediaType
from polarity.types.episode import Episode
from polarity.types.person import Actor, Person
from polarity.types.season import Season

import json

from time import sleep


@dataclass
class Series(MediaType, metaclass=MetaMediaType):
    title: str = None
    id: str = None
    synopsis: str = None
    genres: list[str] = field(default_factory=list)
    year: int = 1970
    images: list = field(default_factory=list)
    season_count: int = 0
    episode_count: int = 0
    people: list[Person] = field(default_factory=list)
    seasons: list[Season] = field(init=False, default_factory=list)
    _extractor: str = field(init=False)
    # False if all series information is extracted, not counting seasons
    # and their respective episodes, True if not
    # Check the wiki for more info
    _partial = True
    # True if all requested seasons and episodes have been extracted,
    # False if not
    _extracted = False

    def __repr__(self) -> str:
        return f'Series({self.title}, {self.id})[{"partial" if self._partial else "full"}]'

    def link_person(self, person: Person) -> None:
        if person not in self.actors:
            self.actors.append(person)

    def link_season(self, season: Season) -> None:
        if season not in self.seasons:
            season._series = self
            self.seasons.append(season)

    def get_season_by_id(self, season_id: str) -> Season:
        match = [s for s in self.seasons if s.id == season_id]
        if match:
            return match[0]

    def get_episode_by_id(self, episode_id: str) -> Episode:
        match = [e for e in self.get_all_episodes() if e.id == episode_id]
        if match:
            return match[0]

    def get_all_episodes(self, pop=False) -> list[Episode]:
        '''
        :param pop: Removes episodes from the lists
        :returns: List with extracted episodes
        '''
        if pop:
            episodes = [
                e for s in self.seasons for e in s.episodes
                if not hasattr(e, '_popped')
            ]
            for episode in episodes:
                episode._popped = None
            return episodes

        return [e for s in self.seasons for e in s.episodes]

    def halt_until_extracted(self):
        '''Sleep until extraction has finished, useful for scripting'''
        while not self._extracted:
            sleep(0.1)