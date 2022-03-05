import json
from dataclasses import asdict


class MetaMediaType(type):
    """Class used to give MediaType classes readibility when printed"""

    def __repr__(self) -> str:
        return self.__name__


class MediaType(metaclass=MetaMediaType):
    def set_values(self, **values) -> None:
        for key, val in values.items():
            setattr(self, key, val)

    def as_dict(self) -> dict:
        return asdict(self)

    def as_json(self, indentation: int = 4) -> str:
        """
        Returns the Series object and children (Season, Episode) objects
        as a JSON string
        :param identation: JSON identation, default: 4
        :return: JSON string
        """
        return json.dumps(asdict(self), indent=indentation)
