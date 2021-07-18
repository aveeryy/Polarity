import re
class Time:
    human_time = r'(?:(?P<h>\d{2}):|)(?P<m>\d{2}):(?P<s>\d{2})\.(?P<ms>\d+)'
    def __init__(self) -> None:
        self.hours = 0
        self.minutes = 0
        self.seconds = 0
        self.milisec = 0

    def __str__(self) -> str:
        return f'{self.hours}:{self.minutes}:{self.seconds}.{self.milisec}'

    def parse_human_time(self, time=str) -> bool:
        self.__time = re.match(self.human_time, time)
        if self.__time is None:
            return False
        if 'h' in self.__time.groupdict():
            self.hours = self.__time.group('h')
        self.minutes = self.__time.group('m')
        self.seconds = self.__time.group('s')
        self.milisec = self.__time.group('ms')
        return True
