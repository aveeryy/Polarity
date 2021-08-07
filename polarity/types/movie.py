from .base import PolarType

class Movie(PolarType):
    def __init__(self) -> None:
        self.title = None
        self.id = None
        self.synopsis = None
        self.actors = []
        self.genres = []
        self.year = 1970
        self.images = []
        self.streams = []