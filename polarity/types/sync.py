from polarity.types.base import PolarType
from polarity.types.series import Series
from polarity.types.season import Season
from polarity.types.episode import Episode

class SyncList:
    def add_item(item: PolarType, extractor: str):
        sync_object = SyncObject()
        sync_object.media_type = type(item)
        if type(item) == Series:
            for season in item.seasons:
                season_object = SyncObject()
                for episode in season.episodes:
                    episode_obj = SyncObject()
                    media_type = 'episode' if not episode.movie else 'movie'
                    episode_obj.id = f'{extractor}/{media_type}-{episode.id}'
                    episode_obj.media_type = Episode
                
    
class SyncObject:
    def __init__(self) -> None:
        self._sync_new_children = True
        self._finished = False
        self._downloaded = False
        self.id = None
        self.media_type = None
        self.children = []
    
    def get_all_grandchildren(self):
        all_grandchildren = []
        for child in self.children:
            if not type(child) == SyncObject or not child.children:
                continue
            all_grandchildren.extend(child.children)
        return all_grandchildren