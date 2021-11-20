from polarity.types.base import MediaType, MetaMediaType
from dataclasses import dataclass, field
import time

@dataclass
class Task:
    name: str = 'GenericTask'
    enable: bool = True
    subtasks: list = field(default_factory=list)
    started = False
    running = False
    completed = False
    start_time = 0
    end_time = 0
    time_elapsed = 0
    
    def start(self) -> None:
        'Sets the task as started and writes the start time'
        self.started = True
        self.running = True
        self.start_time = f'{time.time():.02f}'
        
    def end(self) -> None:
        'Sets tasks as completed and writes the end time'
        self.running = False
        self.completed = True
        self.end_time = f'{time.time():.02f}'
        self.time_taken = self.end_time - self.start_time