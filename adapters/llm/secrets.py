"""Local secret references kept outside ordinary project data."""
import os
import re
import uuid
from pathlib import Path

REF = re.compile(r"^[a-f0-9-]{36}$")

class SecretStore:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, value):
        if not isinstance(value, str) or len(value.strip()) < 8:
            raise ValueError("API key is required")
        ref = str(uuid.uuid4())
        path = self.root / (ref + ".key")
        with path.open("x", encoding="utf-8") as handle:
            handle.write(value.strip())
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return ref

    def get(self, ref):
        if not isinstance(ref, str) or not REF.fullmatch(ref):
            raise ValueError("Invalid credential reference")
        path = (self.root / (ref + ".key")).resolve()
        if path.parent != self.root or not path.is_file():
            raise ValueError("Credential is unavailable")
        return path.read_text(encoding="utf-8").strip()

    def masked(self, ref):
        self.get(ref)
        return "********"
