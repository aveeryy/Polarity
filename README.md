# Polarity
> 🍝 Spaghetti powered, cross-platform mass downloader and metadata extractor for video streaming platforms.

[![DeepSource](https://deepsource.io/gh/Aveeryy/Polarity.svg/?label=active+issues&show_trend=true)](https://deepsource.io/gh/Aveeryy/Polarity/)



## Features
- **Cross-platform** (Linux, Windows, MacOS, Android, anything that can run Python and FFmpeg)
- **Multilanguage**
### Download features
- **Resolution selection**
- **Subtitles support**
- **Custom name formatting**
- **Multi-threaded downloads**
- **External downloader support**
### Other features
- **Search in supported extractors**
- **_(Minimal)_ Live TV support**
<!---

- **Automatically download new episodes**
- **Plex and Kodi Metadata support**
-->


## Installation
- ### [Windows Installation <img src="https://aveeryy.github.io/icons/small/Windows.png" alt="Windows" width="16"/>](https://github.com/Aveeryy/Polarity/wiki/Installing#windows-)
- ### [Android Installation <img src="https://aveeryy.github.io/icons/small/Android.png" alt="Android" width="16"/>](https://github.com/Aveeryy/Polarity/wiki/Installing#android-)

## Supported websites
| | Platforms | Premium support | Subtitles |
|:-:|:-:|:-:|:-:|
| Atresplayer | <img src="https://aveeryy.github.io/icons/small/Windows.png" alt="Windows" width="16"/> <img src="https://aveeryy.github.io/icons/small/Linux.png" alt="Linux" width="16"/> <img src="https://aveeryy.github.io/icons/small/MacOS.png" alt="MacOS" width="16"/> <img src="https://aveeryy.github.io/icons/small/Android.png" alt="Android" width="16"/> | ✔️ | ✔️ |
| Crunchyroll |<img src="https://aveeryy.github.io/icons/small/Windows.png" alt="Windows" width="16"/> <img src="https://aveeryy.github.io/icons/small/Linux.png" alt="Linux" width="16"/> <img src="https://aveeryy.github.io/icons/small/MacOS.png" alt="MacOS" width="16"/> <img src="https://aveeryy.github.io/icons/small/Android.png" alt="Android" width="16"/> | ✔️ | ✔️ |

> Note: "🍝" means in progress

## Configuration
Configuration files are found at:

### Windows
    C:\Users\<username>\.Polarity\
    %userprofile%\.Polarity\
    ~/.Polarity/ (Powershell only)

### Linux
    /home/<username>/.Polarity/
    ~/.Polarity/
     
### Mac OS
    /Users/<username>/.Polarity/
    ~/.Polarity/

## Testing devices
<img src="https://aveeryy.github.io/icons/small/Linux.png" alt="Linux" width="16"/>  **Arch Linux** (latest kernel)

<img src="https://aveeryy.github.io/icons/small/Windows.png" alt="Windows" width="16"/>  **Windows 10** (Ameliorated)

<img src="https://aveeryy.github.io/icons/small/Android.png" alt="Android" width="16"/>  **Android 11** (Termux latest/4.9.118)

<img src="https://aveeryy.github.io/icons/small/Android.png" alt="Android" width="16"/>  **Android 10** (Termux 0.101/4.4.210-Sultan)

## Development roadmap (in order)
- Finish Crunchyroll support ✔
- Crunchyroll bugfixing ✔
- Support for movie formatting ✔
- Language support ✔
- Internal downloader ✔
- Support for external downloaders ✔
- Crunchyroll Beta support ✔
- Search function ✔
- Downloading by id, (example: crunchyroll/series-912874) ✔
- Support for Plex and Kodi metadata files ⚙
- Final bugfixing ❌
- First release ❌
- Automatic synchronization ⚙
- Support for more websites ❌
- Music support ❌

## Legal disclaimer
This application is not affiliated nor endorsed by any of the sites mentioned above. This application enables downloading videos for *offline viewing* which may be forbidden in your country or cause a violation of the Terms of Service of your Internet Service Provider and/or streaming provider. Neither I nor this tool are responsible of your actions and therefore, consequences.

### About Cloudflare and Polarity
Polarity uses [cloudscraper](https://github.com/VeNoMouS/cloudscraper) to bypass Cloudflare protections, by making too much requests your IP address could be blocked by Cloudflare for 24 hours or even more. This can be circunvented by restarting your router if you have a dynamic address, using a proxy / VPN or using a captcha recognition service. If you can't use any of the before mentioned circunventions you will have to wait to use Polarity with that streaming service again.
