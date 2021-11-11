class MediaType:
    @property
    def class_name(self):
        return self.__class__.__name__

    def set_metadata(self, **metadata) -> None:
        for key, val in metadata.items():
            setattr(self, key, val)