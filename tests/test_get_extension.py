import pytest

from polarity.utils import get_extension


@pytest.mark.parametrize(
    "url,expected_ext",
    [
        ("http://thisisanurl.com/file.m3u8", ".m3u8"),
        ("http://thisisanurl.com/file.m3u8?with_a_param=key.key", ".m3u8"),
        (
            "http://this.is.an.url.withsubdomains.com/file.m3u8?with_a_param=key.key&another_param=berries.xml",
            ".m3u8",
        ),
        ("http://thisisanurl.com/without_an_extension", ""),
        ("http://thisdoesnothaveapath.com/", ""),
        ("file:///thisisalocalfile.txt", ".txt"),
        ("ftp://thisisafileinanftpserver:21/document.pdf", ".pdf"),
    ],
)
def test_get_extension(url: str, expected_ext: str):
    assert get_extension(url=url) == expected_ext
