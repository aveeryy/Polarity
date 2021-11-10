from .base import MediaType

class Movie(MediaType):
    title = None
    id = None
    synopsis = None
    actors = []
    genres = []
    year = 1970
    images = []
    streams = []