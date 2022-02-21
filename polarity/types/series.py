from dataclasses import dataclass

from polarity.types.generic import ContentContainer, Content


@dataclass
class Series(ContentContainer):
    synopsis: str = ""
    year: int = 1970
    season_count: int = 0
    episode_count: int = 0

    def __repr__(self) -> str:
        return f"Series({self.title}, {self.id})"

    def link_content(self, content: Content) -> None:
        content._series = self
        return super().link_content(content)
