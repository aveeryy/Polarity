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
        if self.__time.groupdict()['h'] is not None:
            self.hours = int(self.__time.group('h'))
        self.minutes = int(self.__time.group('m'))
        self.seconds = int(self.__time.group('s'))
        self.milisec = int(self.__time.group('ms'))
        return True

    def time_to_unix(self, time=str) -> float:
        self.parse_human_time(time=time)
        self.__milisec = int(str(self.milisec)[0:2]) / 100
        return self.hours * 3600 + self.minutes * 60 + self.seconds + self.__milisec