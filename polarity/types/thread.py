import multiprocessing
import threading
import os

from queue import Queue
from typing import NoReturn


class Thread(threading.Thread):
    def __init__(self, thread_type=None, *args, **kwargs) -> None:
        self.type = thread_type if thread_type is not None else 'Base'
        # Set a base status dictionary
        self.status = dict()
        self.status['running'] = False
        self.status['type'] = thread_type
        self.status['status'] = dict()
        # Set children list
        self.__children = list()
        # Add Process to _ALL_THREADS list / TODO: change name to _ALL_PROCESSES
        from polarity.config import processes
        processes.append(self)
        super().__init__(name=thread_type, *args, **kwargs)

    def __repr__(self) -> str:
        string = f'Thread({self.__class__.__name__})[{self.type}'
        if self.daemon:
            string += ', daemonic'
        string += ']'
        return string

    def set_child(self, child: object) -> None:
        'Makes a Thread a child of the current thread'
        self.__children.append(child)

    def start(self) -> None:
        self.status['running'] = True
        return super().start()
