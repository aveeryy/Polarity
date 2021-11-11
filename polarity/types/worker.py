from polarity.types.thread import Thread
from polarity.utils import get_compatible_extractor, vprint, is_content_id
from polarity.config import lang


class Worker(Thread):
    '''
    ### Worker Process
    1. Takes an URL from an iterable
    2. If an extractor is available for that URL, do extraction
    3. Build a download list using the format_filename function
    '''
    def __init__(self, content_pool: list, worker_id: int) -> None:
        super().__init__(thread_type=self.__class__.__name__,
                         daemon=True,
                         name=f'Worker{worker_id}')

        self.pool = content_pool
        self.url = None

        self.status['type'] = self.__class__.__name__
        # Set base status dictionary
        self.status['status'] = {
            'current_url': None,
            'running': False,
            'tasks': {
                'extraction': {
                    'running': False,
                    'completed': False,
                    'extractor': None,
                },
                'download': {
                    'downloader': None,
                    'downloads_active': 0,
                    'content_downloading': list()
                }
            }
        }

    def run(self):
        self.status['running'] = True
        while self.pool:
            # Pick an URL from the pool
            self.url = self.status['status']['current_url'] = self.pool.pop(0)


            # Get a compatible extractor and if not None, do extraction
            name, extractor = get_compatible_extractor(url=self.url)
            if extractor is None:
                # No extractor available, continue to next item in pool
                vprint(lang['dl']['no_extractor_available'] %
                       (lang['dl']['url'] if not is_content_id(self.url) else
                        lang['dl']['download_id'], self.url),
                       module_name='worker',
                       error_level='error')
                continue
            # Start extraction process
            self.status['status']['tasks']['extraction']['extractor'] = name
            vprint('')
            extracted_info = extractor(
                url=self.url['url'], options=self.options['extraction'][name.lower()]).extract()
            for i in range(0, self.options['download']['downloads_per_url']):
                pass
        self.status['running'] = False
