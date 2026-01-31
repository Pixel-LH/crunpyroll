from .obj import Object

from typing import List, Dict, Any


def _ms_from_value(val: Any) -> int:
    """Normalize start/end to milliseconds (accept seconds or ms)."""
    if val is None:
        return 0
    if isinstance(val, float):
        return int(round(val * 1000)) if val < 10000 else int(round(val))
    v = int(val)
    return v if v > 10000 else v * 1000


class SkipEvent(Object):
    """
    A single skip event (intro, recap, credits, etc.).

    Parameters:
        start_ms (``int``):
            Start time in milliseconds.
        end_ms (``int``):
            End time in milliseconds.
        event_type (``str``):
            Type of the event (e.g. intro, recap, credits, chapter).
    """
    def __init__(self, data: Dict):
        self.start_ms: int = data.get("start_ms", 0)
        self.end_ms: int = data.get("end_ms", 0)
        self.event_type: str = (data.get("event_type") or data.get("type") or "chapter").lower()


class SkipEvents(Object):
    """
    Container of skip events for an episode.

    Parameters:
        events (List of :obj:`~crunpyroll.types.SkipEvent`):
            List of skip events, ordered by start_ms.
    """
    def __init__(self, data: Dict):
        self.events: List["SkipEvent"] = data.get("events", [])

    @classmethod
    def parse(cls, obj: Any) -> "SkipEvents":
        """
        Parse skip-events JSON. Accepts:
        - Crunchyroll format: dict with top-level keys "intro", "recap", "credits", "preview",
          each value being { "start": seconds, "end": seconds, "type": "..." }.
        - A list of objects with start/end (seconds or ms) and type/event_type.
        - A dict with key "skip_events" or "events" containing such a list.
        """
        events: List[SkipEvent] = []
        if isinstance(obj, dict):
            if obj.get("skip_events") is not None or obj.get("events") is not None:
                raw_list = obj.get("skip_events") or obj.get("events") or []
                for item in raw_list if isinstance(raw_list, list) else []:
                    if not isinstance(item, dict):
                        continue
                    start = item.get("start_ms") or item.get("start")
                    end = item.get("end_ms") or item.get("end")
                    event_type = (item.get("event_type") or item.get("type") or "chapter")
                    if isinstance(event_type, str):
                        event_type = event_type.lower()
                    else:
                        event_type = "chapter"
                    events.append(SkipEvent({
                        "start_ms": _ms_from_value(start),
                        "end_ms": _ms_from_value(end),
                        "event_type": event_type,
                    }))
            else:
                for chapter_type in ("intro", "recap", "credits", "preview"):
                    chapter_info = obj.get(chapter_type)
                    if not isinstance(chapter_info, dict):
                        continue
                    start = chapter_info.get("start")
                    end = chapter_info.get("end", start)
                    event_type = (chapter_info.get("type") or chapter_type).lower()
                    events.append(SkipEvent({
                        "start_ms": _ms_from_value(start),
                        "end_ms": _ms_from_value(end),
                        "event_type": event_type,
                    }))
        elif isinstance(obj, list):
            for item in obj:
                if not isinstance(item, dict):
                    continue
                start = item.get("start_ms") or item.get("start")
                end = item.get("end_ms") or item.get("end")
                event_type = (item.get("event_type") or item.get("type") or "chapter")
                if isinstance(event_type, str):
                    event_type = event_type.lower()
                else:
                    event_type = "chapter"
                events.append(SkipEvent({
                    "start_ms": _ms_from_value(start),
                    "end_ms": _ms_from_value(end),
                    "event_type": event_type,
                }))
        events.sort(key=lambda e: e.start_ms)
        return cls({"events": events})


class Chapter(Object):
    """
    A named chapter for download/embedding (Smart Chapters).

    Parameters:
        title (``str``):
            Display title (e.g. "Intro", "Recap", "Chapter 1", "Credits").
        start_time (``float``):
            Start time in seconds.
        end_time (``float``):
            End time in seconds.
    """
    def __init__(self, data: Dict):
        self.title: str = data.get("title", "")
        self.start_time: float = data.get("start_time", 0.0)
        self.end_time: float = data.get("end_time", 0.0)


# Gap threshold: intervals larger than this (ms) are split into separate chapters.
DEFAULT_CHAPTER_GAP_MS = 500


def build_chapter_list(
    events: List["SkipEvent"],
    *,
    gap_ms: int = DEFAULT_CHAPTER_GAP_MS,
    duration_ms: int = 0,
) -> List[Chapter]:
    """
    Build a list of named chapters from skip events (Smart Chapters).

    - Known types (intro, recap, credits) get fixed titles.
    - Main content after intro/recap is named "Chapter 1", "Chapter 2", ...
    - Gaps between events larger than gap_ms become unnamed segments or "Chapter N".

    Parameters:
        events: List of SkipEvent (e.g. from SkipEvents.events).
        gap_ms: Minimum gap (ms) to start a new chapter between events.
        duration_ms: Optional total duration (ms); used to close the last chapter.

    Returns:
        List of Chapter with title, start_time, end_time (in seconds).
    """
    if not events:
        return []
    event_type_titles = {
        "intro": "Intro",
        "recap": "Recap",
        "credits": "Credits",
        "outro": "Credits",
        "preview": "Preview",
    }
    after_intro_recap_ms = max(
        (e.end_ms for e in events if e.event_type in ("intro", "recap")),
        default=0,
    )
    chapters: List[Chapter] = []
    chapter_index = 0
    last_end_ms = 0

    for ev in events:
        start_ms = ev.start_ms
        end_ms = ev.end_ms
        if start_ms > last_end_ms + gap_ms and last_end_ms > 0:
            gap_start_s = last_end_ms / 1000.0
            gap_end_s = start_ms / 1000.0
            if last_end_ms >= after_intro_recap_ms:
                chapter_index += 1
                title = "Chapter " + str(chapter_index)
            else:
                title = "Opening"
            chapters.append(Chapter({
                "title": title,
                "start_time": gap_start_s,
                "end_time": gap_end_s,
            }))
        title = event_type_titles.get(ev.event_type)
        if title is None:
            if start_ms >= after_intro_recap_ms:
                chapter_index += 1
                title = "Chapter " + str(chapter_index)
            else:
                title = "Opening"
        chapters.append(Chapter({
            "title": title,
            "start_time": start_ms / 1000.0,
            "end_time": end_ms / 1000.0,
        }))
        last_end_ms = max(last_end_ms, end_ms)

    if duration_ms > 0 and last_end_ms < duration_ms and last_end_ms > 0:
        if last_end_ms >= after_intro_recap_ms:
            chapter_index += 1
            tail_title = "Chapter " + str(chapter_index)
        else:
            tail_title = "End"
        chapters.append(Chapter({
            "title": tail_title,
            "start_time": last_end_ms / 1000.0,
            "end_time": duration_ms / 1000.0,
        }))
    return chapters
