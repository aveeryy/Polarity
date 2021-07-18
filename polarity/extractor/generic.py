from polarity.extractor import BaseExtractor

class GenericExtractor(BaseExtractor):

    HOST = r'(?P<ext>\.(?:m3u8|m3u))($|[^/.\w\s,])'

    def extract(self) -> dict:
        self.load_info_template('movie')