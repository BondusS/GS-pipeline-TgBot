from __future__ import annotations

from html import escape


def code(value: str) -> str:
    return f"<code>{escape(value)}</code>"


def help_text() -> str:
    return "\n".join(
        [
            "Команды:",
            f"{code('/start')} - старт",
            f"{code('/help')} - помощь",
            f"{code('/path <windows_path>')} - перевести путь в linux и показать структуру",
            f"{code('/pipeline <windows_path>')} - собрать базовый pipeline",
            f"{code('/partition <windows_path>')} - команда для partition",
            f"{code('/train <windows_path>')} - собрать все train/LOD команды",
            f"{code('/merge <windows_path>')} - базовая merge-команда",
            f"{code('/config')} - открыть редактор параметров с inline-кнопками",
            f"{code('/config <section>')} - сразу открыть нужную секцию",
            f"{code('/set section.field value')} - запасной ручной способ изменить параметр",
            f"{code('/reset <section|all>')} - сбросить секцию или весь пресет",
            "",
            "Примеры:",
            code("/pipeline X:\\GaussianSplatting\\data\\RIGs\\GoPro\\10Cams\\20260209\\for_GS_Track03"),
            code("/config"),
            code("/config train"),
            code("/set partition.grid_dim_x 4"),
        ]
    )


def format_project_paths(paths) -> str:
    return (
        f"Windows path:\n{code(paths.windows_path)}\n\n"
        f"Linux path:\n{code(paths.linux_path)}\n\n"
        f"configs: {code(paths.windows_configs_dir)}\n"
        f"images: {code(paths.images)}\n"
        f"partition: {code(paths.partition)}\n"
        f"masks_ununited: {code(paths.masks_ununited)}\n"
        f"masks: {code(paths.masks)}\n"
        f"results/main/blocks: {code(paths.results_main_blocks)}\n"
        f"results/lod/d=2/blocks: {code(paths.results_lod2_blocks)}\n"
        f"results/lod/d=4/blocks: {code(paths.results_lod4_blocks)}"
    )


def split_long_text(text: str, limit: int = 3500) -> list[str]:
    parts: list[str] = []
    remaining = text

    while len(remaining) > limit:
        split_at = remaining.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit
        parts.append(remaining[:split_at])
        remaining = remaining[split_at:].lstrip()

    if remaining:
        parts.append(remaining)

    return parts
