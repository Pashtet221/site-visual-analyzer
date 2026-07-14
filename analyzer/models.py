from dataclasses import dataclass, asdict

@dataclass
class PageTarget:
    name: str
    url: str
    kind: str = "manual"
    source: str = "manual"
    def to_dict(self): return asdict(self)

@dataclass
class CaptureResult:
    name: str
    url: str
    kind: str
    device: str
    screenshot: str | None
    final_url: str
    title: str
    status: str
    http_status: int | None = None
    error: str | None = None
    def to_dict(self): return asdict(self)
