from polarity.utils import sanitize_filename
import pytest

@pytest.mark.parametrize('path,expected', [
    ('¿Cangrejos?', '¿Cangrejos？'),
    ('"Banana" -Monkey', '\'Banana\' -Monkey'),
    ('My GitHub password is ********', 'My GitHub password is ＊＊＊＊＊＊＊＊'),
    ('Me gustan: las hamburguesas y los mazapanes', 'Me gustan- las hamburguesas y los mazapanes'),
    ('|<>?"*:\\/', 'ꟾ˂˃？\'＊---') # Too lazy to write actual phrases, tests everything
])
def test_windows_no_dir(path: str, expected: str):
    'Test sanitization of Windows filenames'
    assert sanitize_filename(path, False, True) == expected
    
@pytest.mark.parametrize('path,expected', [
    (r'C:\This\a_path\and\slashes\won\'t\get\replaced', r'C:\This\a_path\and\slashes\won\'t\get\replaced'),
    (r'D:\but\thi|s\one\has>\weird<\characters?*\\', r'D:\but\thiꟾs\one\has˃\weird˂\characters？＊\\')
])
def test_windows_dir(path: str, expected: str):
    'Test sanitization of Windows directories'
    assert sanitize_filename(path, True, True) == expected
    
# TODO: non-Windows sanitization tests