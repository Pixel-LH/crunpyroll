from .obj import Object
from typing import Dict, Optional

class DRM(Object):
    """
    Info about DRM.

    Parameters:
        key_id (``str``, optional):
            None when absent from the manifest.

        pssh (``str``, optional):
            None when absent from the manifest.
    """
    def __init__(self, data: Optional[Dict]):
        data = data or {}
        self.key_id: Optional[str] = data.get("key_id")
        self.pssh: Optional[str] = data.get("pssh")

class ContentProtection(Object):
    """
    List of Content Protection (DRM) used by Crunchyroll.

    Parameters:
        widevine (:obj:`~crunpyroll.types.DRM`):
            Info about Widevine DRM. Fields are None when not present.

        playready (:obj:`~crunpyroll.types.DRM`):
            Info about PlayReady DRM. Fields are None when not present.
    """
    def __init__(self, data: Optional[Dict]):
        data = data or {}
        self.widevine: "DRM" = DRM(data.get("widevine"))
        self.playready: "DRM" = DRM(data.get("playready"))
