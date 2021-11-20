from dataclasses import dataclass
from polarity.types.base import MediaType, MetaMediaType

@dataclass
class Person(MediaType, metaclass=MetaMediaType):
    name: str
    gender: str
    image: str
    biography: str
    
class Actor(Person):
    character: str

class Director(Person):
    pass

class Artist(Person):
    pass