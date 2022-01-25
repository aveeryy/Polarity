import threading
from typing import Union


class Thread(threading.Thread):
    def __init__(
        self, thread_type: str = None, stack_id: Union[str, int] = None, *args, **kwargs
    ) -> None:
        if "name" not in kwargs:
            kwargs["name"] = thread_type.lower()
            if stack_id is not None:
                kwargs["name"] += f"-{stack_id}"

        self.type = thread_type if thread_type is not None else "Base"
        super().__init__(*args, **kwargs)

    def __repr__(self) -> str:
        string = f"Thread({self.__class__.__name__})[{self.type}"
        if self.daemon:
            string += ", daemonic"
        string += "]"
        return string

    def start(self) -> None:
        return super().start()
