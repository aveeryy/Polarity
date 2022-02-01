############
# Accounts #
############


class AccountCapabilities:
    "Enable cookiejar for the extractor"


class ExtractionLoginRequired:
    """Force logging into the extractor's website before extraction"""


class SearchLoginRequired:
    """Indicate logging-in is required to use the search feature"""


############
# Features #
############


class EnableLiveTV:
    "Add extractor to pool when using livetv mode"


class EnableSearch:
    "Add extractor to pool when using search mode"


class VideoExtractor:
    "Enable VOD-specific extractor features"
