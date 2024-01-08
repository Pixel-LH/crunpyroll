<p align="center">
    <a href="https://github.com/stefanodvx/crunpyroll">
        <img src="https://github.com/stefanodvx/crunpyroll/assets/69367859/255bd391-3a7c-44f1-bf8c-08de275e73e9" alt="Crunpyroll">
    </a>
</p>

---

#### Features 🔥
- Fully async ([httpx](https://www.python-httpx.org/))
- Python 3.7+ support
- Clean and modern code
- Updated to latest Crunchyroll API

---

#### Installation ⚙️
```bash
# Using Git
pip install -U git+https://github.com/stefanodvx/crunpyroll

# Using PyPi (Recommended)
pip install -U crunpyroll
```

---

#### Documentation 📄
The documentation page undergoes automatic updates with each push. To access the latest documentation page, kindly refer to our [Read the Docs](https://crunpyroll.readthedocs.io/) project.

---

#### Example Code ❓
```py3
import crunpyroll
import asyncio

client = crunpyroll.Client(
    email="email",
    password="password",
    locale="it-IT"
)
async def main():
    # Start client and login
    await client.start()
    # Search for Attack on Titan
    query = await client.search("Attack On Titan")
    series_id = query.items[0].id
    print(series_id)
    # Retrieve all seasons of the series
    seasons = await client.get_seasons(series_id)
    print(seasons)

asyncio.run(main())
```

---

#### Downloading content 🔑
Crunchyroll has recently implemented the Widevine and PlayReady **Digital Rights Management (DRM)** systems, which has led to challenges for certain users attempting to download content from the platform. Currently, there are two available methods for downloading content from the platform:
- Using `Client.get_streams` method: this is the latest and 'right' way to get streams. Provided streams will be protected by Widevine and PlayReady DRMs.
- Using `Client.get_old_streams` method: this method will provide access to unprotected streams, eliminating the need for concern regarding DRM.
> [!WARNING]
> It is important to note that this method relies on a deprecated endpoint, and there is a possibility that it may cease to function unexpectedly. We strongly recommend updating your code to incorporate the `Client.get_streams` method for a more reliable and sustainable solution.

Subsequently, the following code provides an illustrative example of obtaining decryption keys through the utilities of the [pywidevine](https://github.com/devine-dl/pywidevine) library and an L3 Content Decryption Module (CDM).
```py3
from pywidevine.cdm import Cdm
from pywidevine.pssh import PSSH
from pywidevine.device import Device
...
device = Device.load("l3cdm.wvd")
cdm = Cdm.from_device(device)
# Get streams of the episode/movie
streams = await client.get_streams("GRVDQ1G4R")
# Get manifest of the format you prefer
manifest = await client.get_manifest(streams.hardsubs[0].url)
# print(manifest)
# Get Widevine PSSH from manifest
pssh = PSSH(manifest.content_protection.widevine.pssh)
session_id = cdm.open()
challenge = cdm.get_license_challenge(session_id, pssh)
license = await client.get_license(
    streams.media_id,
    challenge=challenge,
    token=streams.token
)
cdm.parse_license(session_id, license)
for key in cdm.get_keys(session_id, "CONTENT"):
    print(f"{key.kid.hex}:{key.key.hex()}")
cdm.close(session_id)
```
Output:
```bash
056ec1ca849e350181753cacc9bd404b:2307a188ecd8de3859b71b30791f171d
```
> [!TIP]
> Decryption keys are universally applicable to both video and audio streams, maintaining consistency across all available formats.

---

#### TODO List 📄
- [ ] Add support for token login
- [ ] Add support for visitor view (authless)
- [ ] Add support for Music
- [ ] Add missing documentation
- [ ] Add missing API methods
- [ ] Add support for PlayReady DRM

---

> Stay informed about the latest developments by joining our [Telegram Channel](https://t.me/crunpyroll).