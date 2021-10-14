class FFmpegInput:
    def __init__(self) -> None:
        self.file_path = None
        self.indexes = {
            'file': 0,
            VIDEO: 0,
            AUDIO: 0,
            SUBTITLES: 0,
        }
        self.metadata = {}
        self.hls_stream = False,
        self.convert_to_srt = False
    
    def generate_command(self) -> dict:
        command = {'input': [], 'meta': []}
        if self.hls_stream:
            command['input'] += '-allowed_extensions', 'ALL'
        command['input'] += '-i', self.file_path
        command['meta'] += '-map', f'{self.indexes["file"]}:{VIDEO}?'
        command['meta'] += '-map', f'{self.indexes["file"]}:{AUDIO}?'
        command['meta'] += '-map', f'{self.indexes["file"]}:{SUBTITLES}?'
        for media_type, metadata in self.metadata.items():
            for key, value in metadata.items():
                if value is None:
                    continue
                if type(value) == list:
                    value = value[self.indexes[media_type]]
                command['meta'] += f'-metadata:s:{media_type}:{self.indexes[media_type]}', f'{key}={value}'
        if self.convert_to_srt:
            command['meta'] += f'-c:s:{self.indexes[SUBTITLES]}', 'srt'
        return command

VIDEO = 'v'
AUDIO = 'a'
SUBTITLES = 's'