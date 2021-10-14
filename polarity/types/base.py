import json

class PolarType:
    '''

    '''
    def set_metadata(self, **values):
        for key, value in values.items():
            setattr(self, key, value)