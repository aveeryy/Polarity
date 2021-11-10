import multiprocessing
import os

from queue import Queue

from polarity.config import processes

class Process(multiprocessing.Process):
    
    def __init__(self, process_type=None, *args, **kwargs) -> None:
        self.type = process_type if process_type is not None else 'Base'
        # Set a base status dictionary
        self.status = dict()
        self.status['running'] = False
        self.status['type'] = process_type
        self.status['status'] = dict()
        # Set children list
        self.__children = list()
        # Add Process to _ALL_THREADS list / TODO: change name to _ALL_PROCESSES
        processes.append(self)
        super().__init__(*args, **kwargs)
        
    def __repr__(self) -> str:
        string = f'Process({self.__class__.__name__})[{self.name}'
        if self.daemon:
            string += ', daemonic'
        string += ']'
        return string
    
    def set_child(self, child: object) -> None:
        'Makes a Process a child of the current process, allows stopping a whole tree of Processes'
        self.__children.append(child)

        
    def terminate(self) -> None:
        # Terminate all children processes
        for child in self.__children:
            child.terminate()
        return super().terminate()
        
    def kill(self):
        # Kill all children processes
        for child in self.__children:
            child.kill()
        return super().kill()
    
    def start(self) -> None:
        self.status['running'] = True
        super().start()
