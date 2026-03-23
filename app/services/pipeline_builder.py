from __future__ import annotations

import shlex
from typing import List

from app.services.schemas import (
    DownsampleParams,
    MaskPeopleParams,
    MaskSkyParams,
    MergeDefaults,
    MergeParams,
    PartitionParams,
    PipelineDefaults,
    ProjectPaths,
    TrainParams,
    TrainStageDefaults,
    UniteMasksParams,
)


def q(value: str) -> str:
    return shlex.quote(str(value))


def build_partition_command(paths: ProjectPaths, params: PartitionParams) -> str:
    if params.partition_method not in {"quantile", "uniform", "kd-tree"}:
        raise ValueError("partition_method должен быть quantile, uniform или kd-tree")

    base = [
        "python",
        "utils/sparsetition.py",
        q(paths.sparse),
        str(params.min_points_visible),
        "--output",
        q(paths.partition),
        "--abs_margin",
        str(params.abs_margin),
        "--partition_method",
        params.partition_method,
    ]

    if params.partition_method in {"quantile", "uniform"}:
        base += ["--grid_dim", str(params.grid_dim_x), str(params.grid_dim_y)]
    else:
        if params.partition_count is None:
            raise ValueError("Для kd-tree нужен partition_count")
        base += ["--partition_count", str(params.partition_count)]

    return " ".join(base)


def build_downsample_command(input_dir: str, params: DownsampleParams) -> str:
    return " ".join(
        [
            "python",
            "utils/image_downsample.py",
            q(input_dir),
            "--lanczos",
            "--factor",
            str(params.factor),
        ]
    )


def build_mask_people_command(paths: ProjectPaths, params: MaskPeopleParams) -> str:
    return " ".join(
        [
            "python",
            "utils/mask_people.py",
            "--input-dir",
            q(paths.images),
            "--output-dir",
            q(paths.masks_people),
            "--conf-person",
            str(params.conf_person),
            "--conf-bags",
            str(params.conf_bags),
            "--imgsz",
            str(params.imgsz),
        ]
    )


def build_mask_sky_command(paths: ProjectPaths, params: MaskSkyParams) -> str:
    cmd = [
        "python",
        "mseg_masking/run_local_masking.py",
        "--source-dir",
        q(paths.images),
        "--result-dir",
        q(paths.masks_sky),
        "--classes",
    ]
    cmd.extend(q(class_name) for class_name in params.classes)
    if params.invert:
        cmd.append("--invert")
    return " ".join(cmd)


def build_unite_masks_command(paths: ProjectPaths, params: UniteMasksParams) -> str:
    return " ".join(
        [
            "python",
            "utils/unite_masks.py",
            "--input",
            q(paths.masks_ununited),
            "--output",
            q(paths.masks),
            "--mode",
            q(params.mode),
        ]
    )


def format_block_ids(block_ids: List[int]) -> str:
    return "[" + ",".join(map(str, block_ids)) + "]"


def resolve_partition_block_count(params: PartitionParams) -> int:
    if params.partition_method == "kd-tree":
        if params.partition_count is None:
            raise ValueError("Для kd-tree нужен partition_count")
        return params.partition_count
    return params.grid_dim_x * params.grid_dim_y


def build_train_command(params: TrainParams) -> str:
    if not params.configs:
        raise ValueError("Нужен хотя бы один config")
    if not params.block_ids:
        raise ValueError("Нужен хотя бы один block_id")

    cmd = [
        "python",
        "utils/start_queue_v2.py",
        "--block_ids",
        format_block_ids(params.block_ids),
    ]

    cmd.extend(q(cfg) for cfg in params.configs)

    extra_args: list[str] = []
    if params.version != "main" or params.max_splats is not None or params.sparse_dir:
        extra_args.extend(["--version", q(params.version)])
    if params.max_splats is not None:
        extra_args.extend(["--max_splats", str(params.max_splats)])
    if params.sparse_dir:
        extra_args.extend(["--sparse_dir", q(params.sparse_dir)])

    if extra_args:
        cmd.extend(extra_args)

    return " ".join(cmd)


def resolve_train_stage_params(
    paths: ProjectPaths,
    stage: TrainStageDefaults,
    block_ids: list[int],
) -> TrainParams:
    return TrainParams(
        name=stage.name,
        block_ids=block_ids,
        configs=[f"{paths.linux_configs_dir}/{name}" for name in stage.config_filenames],
        version=stage.version,
        max_splats=stage.max_splats,
        sparse_dir=stage.sparse_dir,
    )


def resolve_train_params(paths: ProjectPaths, defaults: PipelineDefaults) -> list[TrainParams]:
    block_ids = list(range(resolve_partition_block_count(defaults.partition)))
    return [resolve_train_stage_params(paths, stage, block_ids) for stage in defaults.train.stages]


def build_merge_command(params: MergeParams) -> str:
    cmd = [
        "python",
        "utils/merge_citygs_ckpts.py",
        q(params.blocks_dir),
        q(params.partition_path),
        q(params.example_ckpt),
        q(params.output_file),
        "--dataset",
        q(params.dataset),
    ]

    if params.cut_radial_bounds:
        cmd.append("--cut_radial_bounds")

    cmd.extend(
        [
            "--trim_abs_margin",
            str(params.trim_abs_margin),
            "--checkpoint_pattern",
            q(params.checkpoint_pattern),
        ]
    )
    return " ".join(cmd)


def build_merge_params(paths: ProjectPaths, defaults: MergeDefaults) -> MergeParams:
    example_ckpt = (
        f"{paths.results_main_blocks}/block_{defaults.example_block}/checkpoints/"
        f"epoch={defaults.example_epoch}-step={defaults.example_step}.ckpt"
    )
    return MergeParams(
        blocks_dir=paths.results_main_blocks,
        partition_path=paths.partition,
        example_ckpt=example_ckpt,
        output_file=f"{paths.linux_path}/results/main/{defaults.output_name}",
        dataset=paths.linux_path,
        trim_abs_margin=defaults.trim_abs_margin,
        checkpoint_pattern=defaults.checkpoint_pattern,
        cut_radial_bounds=defaults.cut_radial_bounds,
    )


def build_full_pipeline_steps(paths: ProjectPaths, defaults: PipelineDefaults) -> list[tuple[str, str]]:
    train_params = resolve_train_params(paths, defaults)
    merge_params = build_merge_params(paths, defaults.merge)

    steps: list[tuple[str, str]] = [
        ("1. partition", build_partition_command(paths, defaults.partition)),
        (
            "2. replace points3d with dense",
            f"python utils/replace_points3d_with_dense.py {q(paths.linux_path)}",
        ),
        ("3. downsample original images", build_downsample_command(paths.images, defaults.downsample)),
        ("4. people masks", build_mask_people_command(paths, defaults.mask_people)),
        ("5. sky masks", build_mask_sky_command(paths, defaults.mask_sky)),
        ("6. unite masks", build_unite_masks_command(paths, defaults.unite_masks)),
    ]

    for index, params in enumerate(train_params, start=7):
        steps.append((f"{index}. train {params.name}", build_train_command(params)))

    steps.append((f"{len(steps) + 1}. merge example", build_merge_command(merge_params)))
    return steps


def build_full_pipeline_preview(paths: ProjectPaths, defaults: PipelineDefaults) -> str:
    lines = [f'DATASET="{paths.linux_path}"', ""]
    for title, command in build_full_pipeline_steps(paths=paths, defaults=defaults):
        lines.extend([f"# {title}", command, ""])

    return "\n".join(lines).rstrip()
