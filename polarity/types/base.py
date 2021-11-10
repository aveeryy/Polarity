class MediaType:
    @property
    def class_name(self):
        return self.__class__.__name__

    def set_metadata(self, metadata: dict) -> None:
        for key, val in metadata.values():
            setattr(self, key, val)