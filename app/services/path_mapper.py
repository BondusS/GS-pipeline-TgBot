from __future__ import annotations

import re

from app.services.schemas import ProjectPaths


WINDOWS_PREFIX = r"X:\GaussianSplatting\data"
LINUX_PREFIX = "fdata2"


class PathMappingError(ValueError):
    pass


def normalize_windows_path(path: str) -> str:
    path = path.strip().strip('"').strip("'")
    path = path.replace("/", "\\")
    path = re.sub(r"\\+", r"\\", path)
    return path.rstrip("\\")


def windows_to_linux_path(path: str) -> str:
    normalized = normalize_windows_path(path)

    if normalized.lower() == WINDOWS_PREFIX.lower():
        return LINUX_PREFIX

    prefix = WINDOWS_PREFIX + "\\"
    if not normalized.lower().startswith(prefix.lower()):
        raise PathMappingError(
            f"Ожидался путь внутри {WINDOWS_PREFIX}\\ ...\n"
            f"Получен: {path}"
        )

    tail = normalized[len(prefix):]
    linux_tail = tail.replace("\\", "/")
    return f"{LINUX_PREFIX}/{linux_tail}"


def build_project_paths(windows_path: str) -> ProjectPaths:
    normalized_windows_path = normalize_windows_path(windows_path)
    linux_path = windows_to_linux_path(windows_path)

    return ProjectPaths(
        windows_path=normalized_windows_path,
        linux_path=linux_path,
        windows_configs_dir=f"{normalized_windows_path}\\configs",
        linux_configs_dir=f"{linux_path}/configs",
        sparse=f"{linux_path}/sparse",
        images=f"{linux_path}/images",
        images_2=f"{linux_path}/images_2.0",
        images_3=f"{linux_path}/images_3.0",
        images_5=f"{linux_path}/images_5.0",
        partition=f"{linux_path}/partition/main_partition",
        masks_ununited=f"{linux_path}/masks_ununited",
        masks_people=f"{linux_path}/masks_ununited/people",
        masks_sky=f"{linux_path}/masks_ununited/sky",
        masks=f"{linux_path}/masks",
        masks_2=f"{linux_path}/masks_2.0",
        masks_3=f"{linux_path}/masks_3.0",
        masks_5=f"{linux_path}/masks_5.0",
        results_main_blocks=f"{linux_path}/results/main/blocks",
        results_lod2_blocks=f"{linux_path}/results/lod/d=2/blocks",
        results_lod4_blocks=f"{linux_path}/results/lod/d=4/blocks",
    )
