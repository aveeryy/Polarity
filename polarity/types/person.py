from dataclasses import dataclass
from polarity.types.base import MediaType

@dataclass
class Person(MediaType):
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