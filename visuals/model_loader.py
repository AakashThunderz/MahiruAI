from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(slots=True)
class CubismModelInfo:
    name: str
    root_dir: Path
    model_json_path: Path
    texture_path: Path | None
    motion_groups: dict[str, list[str]]
    parameters: list[str]
    lip_sync_ids: list[str]
    eye_blink_ids: list[str]


def load_first_cubism_model(models_root: Path | None = None) -> CubismModelInfo:
    root = models_root or Path(__file__).resolve().parent / "assets" / "models"
    model_json_files = sorted(root.rglob("*.model3.json"))
    if not model_json_files:
        raise FileNotFoundError(f"No Cubism model3.json file was found inside {root}")

    model_json_path = model_json_files[0]
    model_data = read_json(model_json_path)

    display_info_name = model_data.get("FileReferences", {}).get("DisplayInfo")
    display_info = read_json(model_json_path.parent / display_info_name) if display_info_name else {}

    textures = model_data.get("FileReferences", {}).get("Textures", [])
    texture_path = model_json_path.parent / textures[0] if textures else None
    motion_groups = {
        group_name: [item["File"] for item in entries]
        for group_name, entries in model_data.get("FileReferences", {}).get("Motions", {}).items()
    }

    eye_blink_ids: list[str] = []
    lip_sync_ids: list[str] = []
    for group in model_data.get("Groups", []):
        group_name = group.get("Name")
        ids = group.get("Ids", [])
        if group_name == "EyeBlink":
            eye_blink_ids = ids
        if group_name == "LipSync":
            lip_sync_ids = ids

    parameters = [item["Id"] for item in display_info.get("Parameters", [])]
    name = model_json_path.parent.parent.name if model_json_path.parent.name == "runtime" else model_json_path.parent.name

    return CubismModelInfo(
        name=name,
        root_dir=model_json_path.parent,
        model_json_path=model_json_path,
        texture_path=texture_path if texture_path and texture_path.exists() else None,
        motion_groups=motion_groups,
        parameters=parameters,
        lip_sync_ids=lip_sync_ids,
        eye_blink_ids=eye_blink_ids,
    )


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
