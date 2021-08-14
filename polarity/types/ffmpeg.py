class FFmpegInput:
    def __init__(self) -> None:
        self.file_path = None
        self.indexes = {
            'file': 0,
            'v': 0,
            'a': 0,
            's': 0,
        }
        self.metadata = {}
        self.hls_stream = False
    
    def generate_command(self) -> dict:
        command = {'input': [], 'meta': []}
        if self.hls_stream:
            command['input'] += '-allowed_extensions', 'ALL'
        command['input'] += '-i', self.file_path
        command['meta'] += '-map', f'{self.indexes["file"]}:v?'
        command['meta'] += '-map', f'{self.indexes["file"]}:a?'
        command['meta'] += '-map', f'{self.indexes["file"]}:s?'
        for media_type, metadata in self.metadata.items():
            for key, value in metadata.items():
                if value is None:
                    continue
                if type(value) == list:
                    value = value[self.indexes[media_type]]
                command['meta'] += f'-metadata:s:{media_type}:{self.indexes[media_type]}', f'{key}={value}'
        return command

VIDEO = 'v'
AUDIO = 'a'
SUBTITLES = 's'