"""Settings, read from ENGRAM_* environment variables or engram/.env."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]      # the engram/ project directory


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ENGRAM_", env_file=ROOT / ".env", extra="ignore")

    database_url: str = "postgresql://engram:engram@127.0.0.1:5433/engram"
    ollama_url: str = "http://127.0.0.1:11434"
    embed_model: str = "bge-m3"         # must produce vectors of the dimension fixed in sql/001_core.sql (1024)
    s1_model: str = "qwen3:1.7b"        # System 1: one-token judgements (must honour think=false; LR §10)
    s2_model: str = "qwen3:14b"         # System 2: the uncertain middle band, and generation
    draft_model: str | None = None      # a small model that drafts answers the judge checks, e.g. qwen3:1.7b
    judge_model: str | None = None      # the owner's fine-tuned S1 for the decisions it was trained on (`ask`), e.g.
                                        # mlx:mlx-community/Qwen3-1.7B-bf16@data/adapters/v1; default: s1_model
    asr_model: str = "mlx-community/whisper-large-v3-turbo"    # the watch's speech, transcribed here (voice.py)
    data_dir: Path = ROOT / "data"
    owner: str = "kaminski-v"           # whose brain this is; for the example data, an Enron mailbox id
    owner_timezone: str = "America/Chicago"     # how the owner's emails mean "3 pm Friday" (Enron: Houston)
    herald_timezone: str | None = None  # where the watch's wearer is, for quiet hours; default: this Mac's zone

    @property
    def database(self) -> str:
        """This brain's database name, whether database_url is a URL or key=value connection string."""
        from psycopg.conninfo import conninfo_to_dict

        return conninfo_to_dict(self.database_url).get("dbname") or "engram"

    @property
    def enron_dir(self) -> Path:
        return self.data_dir / "raw" / "enron-emails"

    @property
    def enronqa_dir(self) -> Path:
        return self.data_dir / "raw" / "enron-qa"

    @property
    def vault_dir(self) -> Path:
        """The brain's Obsidian vault: one per brain (database)."""
        return self.data_dir / "vault" / self.database


    @property
    def diplomat_peers(self) -> Path:
        """Other secretaries the Diplomat may talk to: {name: {url, token}}, agreed out of band (diplomat.py)."""
        return self.data_dir / "diplomat" / "peers.json"

    @property
    def watch_file(self) -> Path:
        """Paired watches (token hashes) and the pending pairing code."""
        return self.data_dir / "watch.json"

    @property
    def profiles_file(self) -> Path:
        """The brains this machine's page can open: names, databases, passphrase hashes (profiles.py)."""
        return self.data_dir / "profiles.json"

    @property
    def qmsum_dir(self) -> Path:
        return self.data_dir / "raw" / "qmsum"

    @property
    def workbench_dir(self) -> Path:
        return self.data_dir / "raw" / "workbench"      # a clone of github.com/olly-styles/WorkBench


settings = Settings()
