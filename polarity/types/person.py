from dataclasses import dataclass
from polarity.types.base import MediaType, MetaMediaType


@dataclass
class Person(MediaType, metaclass=MetaMediaType):
    name: str
    gender: str
    image: str
    biography: str


@dataclass
class Actor(Person):
    character: str


class Director(Person):
    pass


@dataclass
class Artist(Person):
    album_artist: bool = False


GENDER_MALE = "Male"
GENDER_FEMALE = "Female"
GENDER_NON_BINARY = "Non-binary"
