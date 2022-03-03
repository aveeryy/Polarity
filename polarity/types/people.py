from polarity.types.base import MediaType, MetaMediaType

# TODO: finish


class Person(MediaType, metaclass=MetaMediaType):
    name: str
