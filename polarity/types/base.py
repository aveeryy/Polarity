import json

class PolarType:
    def set_metadata(self, **values):
        for key, value in values.items():
            self._set_value(key=key, value=value)

    def _set_value(self, key, value):
        setattr(self, key, value)