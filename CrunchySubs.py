from polarity.extractor.crunchyroll import CrunchyrollExtractor
from polarity.utils import normalize_integer
from polarity import __version__ as __polarity__
import cloudscraper
import os
import shutil
import subprocess
import sys

__version__ = '2021.05.28'

class CrunchySubs():
    def __init__(self, url=str):
        # Crunchyroll code: (mkvmerge language, language name)
        self.mkvmerge_langs = {
            'enUS': ('en-US', 'English (USA)'),
            'esES': ('es-ES', 'Español (España)'),
            'esLA': ('es-419', 'Español (América Latina)'),
            'frFR': ('fr-FR', 'Français (France)'),
            'deDE': ('de-DE', 'Deutsch'),
            'itIT': ('it-IT', 'Italiano'),
            'ptBR': ('pt-BR', 'Português (Brasil)'),
            'arME': ('ar-SA', 'العربية'),
            'ruRU': ('ru-RU', 'Русский')
        }
        self.url = url
        if sys.platform == 'win32':
            self.b = '\\'
        else:
            self.b = '/'
        # Create a cloudscraper scraper and a CrunchyrollExtractor object
        self.scraper = cloudscraper.create_scraper()
        self.extractor = CrunchyrollExtractor(
            self.url,
            options={
                'subs_language': ['all'],
                'spoof_us_session': True
                }
            )
        self.data = self.extractor.extract()
        for season in self.data['seasons']:
            for episode in season['episodes']:
                self.subt_list = []
                for subt in episode['extra_subs']:
                    self.file_name = f'{self.data["title"]} S{normalize_integer(season["season_number"])}E{normalize_integer(episode["episode_number"])} - {subt["internal_code"]}'
                    self.subt_list.append((self.file_name, subt['url'], subt['internal_code']))
                    # Download and write subtitles
                    with open(self.file_name + '.ass', 'wb') as subt_file:
                        self.subt_data = self.scraper.get(subt['url']).content
                        subt_file.write(self.subt_data)
                        print('[crunchysubs] successfully written file "%s"' % self.file_name + '.ass')
                if shutil.which('mkvmerge'):
                    print('[crunchysubs] merging into a container')
                    self.subt_list_ordered = [y for x in self.mkvmerge_langs for y in self.subt_list if x == y[2]]
                    # Build mkvmerge command
                    self.arg_list = ['mkvmerge', '--quiet']
                    self.output = f'{self.data["title"]} S{normalize_integer(season["season_number"])}E{normalize_integer(episode["episode_number"])}' + '.mks'
                    self.arg_list.extend(['--output', self.output])
                    for lang_file, url, lang in self.subt_list_ordered:
                        self.arg_list.extend([
                            '--language',
                            '0:' + self.mkvmerge_langs[lang][0],
                            '--track-name',
                            '0:' + self.mkvmerge_langs[lang][1],
                            f'{os.getcwd()}{self.b}{lang_file}.ass'
                        ])
                    self.arg_list.append('--track-order')
                    self.track_order = ''
                    for i in range(len(self.subt_list)):
                        self.track_order += f'{i}:0,'
                    # Strip last comma
                    self.arg_list.append(self.track_order[:-1])
                    subprocess.run(self.arg_list)
                    for i in self.subt_list:
                        os.remove(i[0] + '.ass')
                else:
                    print('[crunchysubs/warning] skipping merging into a container. mkvmerge not installed')
                

if __name__ == '__main__':
    print('[crunchysubs] using CrunchySubs %s' % __version__)
    print('[crunchysubs] using Polarity %s' % __polarity__)
    CrunchySubs(sys.argv[1])