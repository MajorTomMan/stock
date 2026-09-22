from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_url: str
    raw_data_dir: Path
    http_timeout_seconds: int

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=os.getenv(
                "DATABASE_URL",
                "postgresql://major:majortom@127.0.0.1:10007/stock",
            ),
            raw_data_dir=Path(os.getenv("RAW_DATA_DIR", "./data/raw")),
            http_timeout_seconds=int(os.getenv("HTTP_TIMEOUT_SECONDS", "40")),
        )
