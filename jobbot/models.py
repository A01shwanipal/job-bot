from dataclasses import dataclass


@dataclass
class Job:
    source: str
    title: str
    company: str
    url: str
    location: str = ""
    description: str = ""
    posted_at: str | None = None  # ISO-8601, UTC
    external_id: str = ""
