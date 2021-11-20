class MetaMediaType(type):
    '''Class used to give MediaType classes readibility when printed'''
    def __repr__(self) -> str:
        return self.__name__

class MediaType:
    def set_metadata(self, **metadata) -> None:
        for key, val in metadata.items():
            setattr(self, key, val)