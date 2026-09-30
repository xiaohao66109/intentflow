"""Schema-driven methods with explicit human review."""
import json
from pathlib import Path
import yaml
from jsonschema import Draft202012Validator

SKILLS = Path(__file__).resolve().parents[1] / "skills"

def catalog():
    return [load(p.name) for p in sorted(SKILLS.iterdir()) if (p / "skill.yaml").is_file()]

def load(skill_id):
    if skill_id not in {p.name for p in SKILLS.iterdir() if (p / "skill.yaml").is_file()}:
        raise ValueError("Unknown skill")
    root = SKILLS / skill_id
    metadata = yaml.safe_load((root / "skill.yaml").read_text(encoding="utf-8"))
    return {**metadata, "instructions": (root / "instructions.md").read_text(encoding="utf-8"),
            "input_schema": json.loads((root / "input.schema.json").read_text(encoding="utf-8")),
            "output_schema": json.loads((root / "output.schema.json").read_text(encoding="utf-8")),
            "checklist": yaml.safe_load((root / "checklist.yaml").read_text(encoding="utf-8"))}

def validate(schema, data):
    errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: str(e.path))
    if errors:
        raise ValueError("; ".join(f"{'.'.join(map(str,e.path)) or 'input'}: {e.message}" for e in errors))
