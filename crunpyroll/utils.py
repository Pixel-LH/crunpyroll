from typing import Optional, List, Dict
from datetime import datetime
from unittest import installHandler
from uuid import uuid4

PUBLIC_TOKEN = "Ym1icmt4eXgzZDd1NmpzZnlsYTQ6QUlONEQ1VkVfY3Awd1Z6Zk5vUDBZcUhVcllGcDloU2c="

APP_VERSION = "3.59.0"

DEVICE_NAME = "iPhone"
DEVICE_TYPE = "iPhone 14"
DEVICE_ID = str(uuid4())

WIDEVINE_UUID = "urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed"
PLAYREADY_UUID = "urn:uuid:9a04f079-9840-4286-ab92-e65be0885f95"

def get_api_headers(headers: Optional[Dict]) -> Dict:
    return {
        "Connection": "Keep-Alive",
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        "User-Agent": "Crunchyroll/ANDROIDTV/3.42.1_22267 (Android 16; en-US; sdk_gphone64_x86_64)",
    } | (headers or {})

def parse_segments(repr: Dict, template: Dict) -> List[str]:
    time = 0
    segments = []
    base_url = repr["BaseURL"]
    representation_id = repr["@id"]
    start_number = int(template["@startNumber"])
    initialization_url = format_segment_url(
        url=base_url + template["@initialization"],
        obj={"RepresentationID": representation_id}
    )
    segments.append(initialization_url)
    #print(f"template: {template}")
    templates = template["SegmentTimeline"]["S"]
    if not isinstance(templates, list):
        repeat = int(templates.get("@r", 0)) + 1
        duration = int(templates.get("@d"))
        time += repeat * duration
        for _ in range(repeat):
            number = start_number + len(segments) - 1
            segment_url = format_segment_url(
                url=base_url + template["@media"],
                obj={
                    "Number": str(number),
                    "RepresentationID": representation_id
                }
            )
            segments.append(segment_url)
    else:
        for segment in template["SegmentTimeline"]["S"]:
            try:
                repeat = int(segment.get("@r", 0)) + 1
                duration = int(segment.get("@d"))
                time += repeat * duration
                for _ in range(repeat):
                    number = start_number + len(segments) - 1
                    segment_url = format_segment_url(
                        url=base_url + template["@media"],
                        obj={
                            "Number": str(number),
                            "RepresentationID": representation_id
                        }
                    )
                    segments.append(segment_url)
            except Exception as e:
                print(f"segment: {segment} | Error: {e}")
                raise e
    return segments

def format_segment_url(url: str, obj: Dict) -> str:
    for key, value in obj.items():
        url = url.replace(f"${key}$", value)
    return url

def get_date() -> datetime: 
    return datetime.utcnow()

def date_to_str(date: datetime) -> Optional[str]: 
    try:
        return "{}-{}-{}T{}:{}:{}Z".format(
            date.year, date.month,
            date.day, date.hour,
            date.minute, date.second
        )
    except Exception:
        return

def str_to_date(string: str) -> Optional[datetime]:
    try:
        return datetime.strptime(
            string,
            "%Y-%m-%dT%H:%M:%SZ"
        )
    except Exception:
        return
