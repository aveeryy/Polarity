class Episode:
    def __init__(self) -> None:
        self.title = None
        self.id = None
        self.synopsis = None
        self.number = 0
        self.streams = []
        self._parent = None