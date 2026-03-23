from __future__ import annotations

from dataclasses import asdict, fields, is_dataclass, replace
from pathlib import Path
from typing import Any, get_type_hints

import yaml
from pydantic import TypeAdapter, ValidationError

from app.services.schemas import PipelineDefaults

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_PRESET_PATH = PROJECT_ROOT / "presets" / "rig_default.yaml"
RUNTIME_PRESET_PATH = PROJECT_ROOT / "presets" / "runtime.yaml"


class PipelineDefaultsError(ValueError):
    pass


def load_pipeline_defaults() -> PipelineDefaults:
    defaults = _load_base_pipeline_defaults()

    if RUNTIME_PRESET_PATH.exists():
        runtime_data = _normalize_legacy_config(_read_yaml_file(RUNTIME_PRESET_PATH))
        defaults = _merge_dataclass(defaults, runtime_data, "root")

    return defaults


def load_pipeline_defaults_section(section: str) -> Any:
    defaults = load_pipeline_defaults()
    section_name = normalize_section_name(section)
    return getattr(defaults, section_name)


def save_pipeline_defaults(defaults: PipelineDefaults) -> None:
    RUNTIME_PRESET_PATH.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_PRESET_PATH.write_text(
        yaml.safe_dump(
            asdict(defaults),
            allow_unicode=False,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def set_pipeline_default(key_path: str, raw_value: str) -> tuple[PipelineDefaults, str, Any]:
    defaults = load_pipeline_defaults()
    parts = key_path.split(".")
    if len(parts) != 2:
        raise PipelineDefaultsError("Ключ должен быть в формате section.field")

    section_name, field_name = normalize_section_name(parts[0]), parts[1].strip()
    if not field_name:
        raise PipelineDefaultsError("После section нужен field")

    section = getattr(defaults, section_name)
    section_type_hints = get_type_hints(type(section))
    if field_name not in section_type_hints:
        raise PipelineDefaultsError(f"Неизвестное поле: {section_name}.{field_name}")

    parsed_value = _parse_value(raw_value)
    validated_value = _validate_value(section_type_hints[field_name], parsed_value, f"{section_name}.{field_name}")
    updated_section = replace(section, **{field_name: validated_value})
    updated_defaults = replace(defaults, **{section_name: updated_section})
    save_pipeline_defaults(updated_defaults)
    return updated_defaults, f"{section_name}.{field_name}", validated_value


def reset_pipeline_defaults(section: str | None = None) -> PipelineDefaults:
    if section is None or section.strip().lower() == "all":
        defaults = _load_base_pipeline_defaults()
        save_pipeline_defaults(defaults)
        return defaults

    section_name = normalize_section_name(section)
    defaults = load_pipeline_defaults()
    base_defaults = _load_base_pipeline_defaults()
    updated_defaults = replace(defaults, **{section_name: getattr(base_defaults, section_name)})
    save_pipeline_defaults(updated_defaults)
    return updated_defaults


def render_pipeline_defaults(defaults: PipelineDefaults, section: str | None = None) -> str:
    data: Any
    if section:
        section_name = normalize_section_name(section)
        data = asdict(getattr(defaults, section_name))
    else:
        data = asdict(defaults)

    return yaml.safe_dump(
        data,
        allow_unicode=False,
        sort_keys=False,
    ).strip()


def render_pipeline_sections(defaults: PipelineDefaults) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for field in fields(defaults):
        items.append(
            (
                field.name,
                yaml.safe_dump(
                    asdict(getattr(defaults, field.name)),
                    allow_unicode=False,
                    sort_keys=False,
                ).strip(),
            )
        )
    return items


def normalize_section_name(section: str) -> str:
    normalized = section.strip().lower().replace("-", "_")
    valid_sections = {field.name for field in fields(PipelineDefaults)}
    if normalized not in valid_sections:
        allowed = ", ".join(sorted(valid_sections))
        raise PipelineDefaultsError(f"Неизвестная секция: {section}. Доступно: {allowed}")
    return normalized


def _load_base_pipeline_defaults() -> PipelineDefaults:
    defaults = PipelineDefaults()
    if BASE_PRESET_PATH.exists():
        base_data = _normalize_legacy_config(_read_yaml_file(BASE_PRESET_PATH))
        defaults = _merge_dataclass(defaults, base_data, "root")
    return defaults


def _normalize_legacy_config(data: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(data)
    train = normalized.get("train")
    if isinstance(train, dict):
        train_normalized = dict(train)
        legacy_configs = train_normalized.pop("configs", None)
        train_normalized.pop("block_ids", None)
        train_normalized.pop("version", None)
        if legacy_configs is not None and "config_filenames" not in train_normalized:
            train_normalized["config_filenames"] = [Path(str(item)).name for item in legacy_configs]
        normalized["train"] = train_normalized
    return normalized


def _read_yaml_file(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        raise PipelineDefaultsError(f"Не удалось прочитать {path}: {e}") from e

    if not raw.strip():
        return {}

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as e:
        raise PipelineDefaultsError(f"YAML в {path} сломан: {e}") from e

    if data is None:
        return {}
    if not isinstance(data, dict):
        raise PipelineDefaultsError(f"Ожидался YAML-объект в {path}")
    return data


def _merge_dataclass(instance: Any, updates: dict[str, Any], path: str) -> Any:
    if not isinstance(updates, dict):
        raise PipelineDefaultsError(f"Ожидался объект для {path}")

    field_map = {field.name: field for field in fields(instance)}
    type_hints = get_type_hints(type(instance))
    unknown = sorted(set(updates) - set(field_map))
    if unknown:
        raise PipelineDefaultsError(f"Неизвестные поля в {path}: {', '.join(unknown)}")

    changed: dict[str, Any] = {}
    for field_name, raw_value in updates.items():
        current_value = getattr(instance, field_name)
        field_path = f"{path}.{field_name}" if path != "root" else field_name
        if is_dataclass(current_value):
            changed[field_name] = _merge_dataclass(current_value, raw_value, field_path)
            continue
        changed[field_name] = _validate_value(type_hints[field_name], raw_value, field_path)

    return replace(instance, **changed)


def _validate_value(annotation: Any, value: Any, field_path: str) -> Any:
    try:
        return TypeAdapter(annotation).validate_python(value)
    except ValidationError as e:
        raise PipelineDefaultsError(f"Некорректное значение для {field_path}: {e}") from e


def _parse_value(raw_value: str) -> Any:
    value = raw_value.strip()
    if not value:
        raise PipelineDefaultsError("После ключа нужно передать значение")

    try:
        return yaml.safe_load(value)
    except yaml.YAMLError as e:
        raise PipelineDefaultsError(f"Не удалось разобрать значение YAML: {e}") from e
