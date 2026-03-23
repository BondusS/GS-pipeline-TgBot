from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from app.services.schemas import PartitionParams, ProjectPaths, TrainDefaults

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ProjectConfigsError(ValueError):
    pass


@dataclass(slots=True)
class ProjectConfigsStatus:
    target_dir: Path
    expected_files: list[str]
    missing_files: list[str]

    @property
    def exists(self) -> bool:
        return not self.missing_files


def get_project_configs_status(
    paths: ProjectPaths,
    train: TrainDefaults,
    partition: PartitionParams,
) -> ProjectConfigsStatus:
    target_dir = Path(paths.windows_configs_dir)
    expected_files = train.config_filenames
    missing_files = [
        name
        for name in expected_files
        if _config_file_needs_render(target_dir / name, paths, train, partition)
    ]
    return ProjectConfigsStatus(
        target_dir=target_dir,
        expected_files=expected_files,
        missing_files=missing_files,
    )


def create_project_configs(
    paths: ProjectPaths,
    train: TrainDefaults,
    partition: PartitionParams,
) -> ProjectConfigsStatus:
    status = get_project_configs_status(paths, train, partition)
    status.target_dir.mkdir(parents=True, exist_ok=True)

    for file_name in status.missing_files:
        template_path = PROJECT_ROOT / file_name
        if not template_path.exists():
            raise ProjectConfigsError(f"Не найден шаблон {template_path}")
        rendered = render_project_config(template_path, paths, train, partition)
        (status.target_dir / file_name).write_text(rendered, encoding="utf-8")

    return get_project_configs_status(paths, train, partition)


def render_project_config(
    template_path: Path,
    paths: ProjectPaths,
    train: TrainDefaults,
    partition: PartitionParams,
) -> str:
    try:
        template = yaml.safe_load(template_path.read_text(encoding="utf-8"))
    except OSError as e:
        raise ProjectConfigsError(f"Не удалось прочитать шаблон {template_path}: {e}") from e
    except yaml.YAMLError as e:
        raise ProjectConfigsError(f"Шаблон {template_path} сломан: {e}") from e

    if not isinstance(template, dict):
        raise ProjectConfigsError(f"Шаблон {template_path} должен быть YAML-объектом")

    rendered = _replace_path_placeholder(template, paths.linux_path)
    block_dim_x, block_dim_y = _resolve_block_dim(train, partition)

    try:
        rendered["data"]["path"] = paths.linux_path
        rendered["data"]["parser"]["init_args"]["block_dim"] = [block_dim_x, block_dim_y]
        rendered["output"] = f"{paths.linux_path}/"
    except KeyError as e:
        raise ProjectConfigsError(f"В шаблоне {template_path.name} не найден обязательный ключ: {e}") from e

    return yaml.safe_dump(rendered, allow_unicode=False, sort_keys=False)


def _replace_path_placeholder(value, linux_path: str):
    if isinstance(value, dict):
        return {key: _replace_path_placeholder(item, linux_path) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_path_placeholder(item, linux_path) for item in value]
    if isinstance(value, str):
        return value.replace("YOUR PATH HERE", linux_path)
    return value


def _resolve_block_dim(train: TrainDefaults, partition: PartitionParams) -> tuple[int, int]:
    block_dim_x = train.block_dim_x if train.block_dim_x is not None else partition.grid_dim_x
    block_dim_y = train.block_dim_y if train.block_dim_y is not None else partition.grid_dim_y
    return block_dim_x, block_dim_y


def _config_file_needs_render(
    path: Path,
    paths: ProjectPaths,
    train: TrainDefaults,
    partition: PartitionParams,
) -> bool:
    if not path.exists():
        return True
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return True
    if "YOUR PATH HERE" in text or "YOUR DIM HERE" in text:
        return True

    template_path = PROJECT_ROOT / path.name
    if not template_path.exists():
        return False

    try:
        actual = yaml.safe_load(text)
        expected = yaml.safe_load(render_project_config(template_path, paths, train, partition))
    except (yaml.YAMLError, ProjectConfigsError, OSError):
        return True

    return actual != expected
