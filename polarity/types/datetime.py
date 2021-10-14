from polarity.utils import normalize_integer

import re

class Time:
    human_time = r'(?:(?P<h>\d{2}):|)(?P<m>\d{2}):(?P<s>\d{2})\.(?P<ms>\d+)'
    def __init__(self) -> None:
        self.hours = 0
        self.minutes = 0
        self.seconds = 0
        self.milisec = 0

    def __str__(self) -> str:
        hours = normalize_integer(self.hours)
        minutes = normalize_integer(self.minutes)
        seconds = normalize_integer(self.seconds)
        milisec = normalize_integer(self.milisec)
        return f'{(hours)}:{minutes}:{seconds}.{milisec}'

    def from_human_time(self, time=str):
        self.__time = re.match(self.human_time, time)
        if self.__time is None:
            return
        if self.__time.groupdict()['h'] is not None:
            self.hours = int(self.__time.group('h'))
        self.minutes = int(self.__time.group('m'))
        self.seconds = int(self.__time.group('s'))
        self.milisec = int(self.__time.group('ms'))
        return self

    @classmethod
    def time_to_unix(self, time=str) -> float:
        self.from_human_time(time=time)
        self.__milisec = int(str(self.milisec)[0:2]) / 100
        return self.hours * 3600 + self.minutes * 60 + self.seconds + self.__milisec