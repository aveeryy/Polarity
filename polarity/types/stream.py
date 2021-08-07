from .base import PolarType

class Stream(PolarType):
    '''
    ### Stream guidelines:
    - Languages' names must be the actual name in that language
    
        >>> ...
        # Bad
        >>> self.name = 'Spanish'
        # Good
        >>> self.name = 'Español'
    - Languages' codes must be [ISO 639-2 codes](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes)
    - On extra_* streams 
    '''
    def __init__(self) -> None:

        self.url = None
        self.id = None
        self.preferred = False
        self.name = None
        self.language = None
        self.audio_name = None
        self.audio_language = None
        self.sub_name = None
        self.sub_language = None
        self.extra_audio = False
        self.extra_sub = False
        
    def set_multilanguage_flag(self) -> None:
        '''
        Set a multiaudio flag if the main stream has more than one audio / subtitle stream
        
        This makes the *_language and *_name variables an iterable
        
        Values of these must be in order, i.e:
        - Audio stream 0 is English, stream 1 is Spanish
        
        >>> self.stream.audio_language = ['eng', 'spa']
        >>> self.stream.audio_name = ['English', 'Español']
        '''
        self.multi_lang = True
        self.audio_name = []
        self.audio_language = []
        self.sub_name = []
        self.sub_language = []