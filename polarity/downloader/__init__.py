from .penguin import PenguinDownloader

DOWNLOADERS = {
    name.replace("Downloader", ""): klass
    for name, klass in globals().items()
    if "Downloader" in name
}
