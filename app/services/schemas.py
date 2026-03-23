from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ProjectPaths:
    windows_path: str
    linux_path: str
    windows_configs_dir: str
    linux_configs_dir: str
    sparse: str
    images: str
    images_2: str
    images_3: str
    images_5: str
    partition: str
    masks_ununited: str
    masks_people: str
    masks_sky: str
    masks: str
    masks_2: str
    masks_3: str
    masks_5: str
    results_main_blocks: str
    results_lod2_blocks: str
    results_lod4_blocks: str


@dataclass(slots=True)
class PartitionParams:
    min_points_visible: int = 50
    abs_margin: float = 1.0
    partition_method: str = "quantile"
    grid_dim_x: int = 3
    grid_dim_y: int = 3
    partition_count: int | None = None


@dataclass(slots=True)
class DownsampleParams:
    factor: float = 2.0


@dataclass(slots=True)
class MaskPeopleParams:
    conf_person: float = 0.35
    conf_bags: float = 0.35
    imgsz: int = 1280


@dataclass(slots=True)
class MaskSkyParams:
    classes: list[str] = field(default_factory=lambda: ["sky"])
    invert: bool = True


@dataclass(slots=True)
class UniteMasksParams:
    mode: str = "and"


@dataclass(slots=True)
class TrainStageDefaults:
    name: str
    config_filenames: list[str]
    version: str
    max_splats: int | None = None
    sparse_dir: str | None = None


def default_train_stages() -> list[TrainStageDefaults]:
    return [
        TrainStageDefaults(
            name="main",
            config_filenames=["BASE_RIG_CONF_D5.yaml", "BASE_RIG_CONF_D3.yaml", "BASE_RIG_CONF_D2.yaml"],
            version="main",
        ),
        TrainStageDefaults(
            name="lod 1",
            config_filenames=["BASE_RIG_CONF_D5.yaml", "BASE_RIG_CONF_D3.yaml"],
            version="lod/d=2",
            max_splats=4_000_000,
        ),
        TrainStageDefaults(
            name="lod 2",
            config_filenames=["BASE_RIG_CONF_D5.yaml", "BASE_RIG_CONF_D3.yaml"],
            version="lod/d=4",
            max_splats=2_000_000,
        ),
        TrainStageDefaults(
            name="lod 3",
            config_filenames=["BASE_RIG_CONF_D5.yaml"],
            version="lod/d=8",
            max_splats=1_000_000,
        ),
        TrainStageDefaults(
            name="lod 4",
            config_filenames=["LOD_RIG_CONF_D5.yaml"],
            version="lod/d=16",
            max_splats=500_000,
        ),
        TrainStageDefaults(
            name="lod 6",
            config_filenames=["LOD_RIG_CONF_D5.yaml"],
            version="lod/d=64",
            max_splats=125_000,
            sparse_dir="sparse_raz",
        ),
        TrainStageDefaults(
            name="lod 8",
            config_filenames=["LOD_RIG_CONF_D5.yaml"],
            version="lod/d=256",
            max_splats=40_000,
            sparse_dir="sparse_raz",
        ),
    ]


@dataclass(slots=True)
class TrainDefaults:
    config_filenames: list[str] = field(
        default_factory=lambda: [
            "BASE_RIG_CONF_D2.yaml",
            "BASE_RIG_CONF_D3.yaml",
            "BASE_RIG_CONF_D5.yaml",
            "LOD_RIG_CONF_D5.yaml",
        ]
    )
    stages: list[TrainStageDefaults] = field(default_factory=default_train_stages)
    block_dim_x: int | None = None
    block_dim_y: int | None = None


@dataclass(slots=True)
class TrainParams:
    name: str
    block_ids: list[int]
    configs: list[str]
    version: str
    max_splats: int | None = None
    sparse_dir: str | None = None


@dataclass(slots=True)
class MergeDefaults:
    trim_abs_margin: float = 1.0
    checkpoint_pattern: str = "step=latest_locally"
    cut_radial_bounds: bool = True
    output_name: str = "point_cloud_2.ply"
    example_block: int = 0
    example_epoch: int = 80
    example_step: int = 120560


@dataclass(slots=True)
class MergeParams:
    blocks_dir: str
    partition_path: str
    example_ckpt: str
    output_file: str
    dataset: str
    trim_abs_margin: float = 1.0
    checkpoint_pattern: str = "step=latest_locally"
    cut_radial_bounds: bool = True


@dataclass(slots=True)
class PipelineDefaults:
    partition: PartitionParams = field(default_factory=PartitionParams)
    downsample: DownsampleParams = field(default_factory=DownsampleParams)
    mask_people: MaskPeopleParams = field(default_factory=MaskPeopleParams)
    mask_sky: MaskSkyParams = field(default_factory=MaskSkyParams)
    unite_masks: UniteMasksParams = field(default_factory=UniteMasksParams)
    train: TrainDefaults = field(default_factory=TrainDefaults)
    merge: MergeDefaults = field(default_factory=MergeDefaults)
