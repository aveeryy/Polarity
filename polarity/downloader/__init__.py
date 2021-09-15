from .penguin import PenguinDownloader

DOWNLOADERS = {
    name.replace('Downloader', '').lower():
    klass
    for name, klass
    in globals().items()
    if 'Downloader' in name
    }

__DOWNLOADERS__ = {
    name.replace('Downloader', ''):
    klass
    for name, klass
    in globals().items()
    if 'Downloader' in name
    }