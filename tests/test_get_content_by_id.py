from polarity.types.content import Content, ContentContainer
from polarity.types import Series, Season, Episode

import pytest

main = Series("no", "main_thing")
second = Season("nah", "season_test")
third = ContentContainer("yes", "001029")

a = Episode("Mod", "dsjadsa")
b = Episode("ds", "3829")
c = Content("rrd", "content")

# build the tree
# main
# |_ second
# |  |_ a
# |  |_ b
# |
# |_ third
#    |_ c

main.link_content(second)
main.link_content(third)

second.link_content(a)
second.link_content(b)
# temporary
third.content = [c]


@pytest.mark.parametrize(
    "id,expected",
    [
        ("dsjadsa", a),
        ("3829", b),
        ("content", c),
        # also test for contentcontainers
        ("season_test", second),
        ("001029", third),
    ],
)
def test(id, expected):
    assert main.get_content_by_id(id) == expected
