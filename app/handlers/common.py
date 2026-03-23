from __future__ import annotations

import logging
import secrets
from dataclasses import fields
from html import escape

import yaml
from aiogram import F, Router
from aiogram.filters import BaseFilter, Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import settings
from app.services.path_mapper import PathMappingError, build_project_paths
from app.services.pipeline_builder import (
    build_full_pipeline_steps,
    build_merge_command,
    build_merge_params,
    build_partition_command,
    build_train_command,
    resolve_train_params,
)
from app.services.pipeline_defaults import (
    PipelineDefaultsError,
    load_pipeline_defaults,
    normalize_section_name,
    render_pipeline_defaults,
    reset_pipeline_defaults,
    set_pipeline_default,
)
from app.services.project_configs import (
    ProjectConfigsError,
    create_project_configs,
    get_project_configs_status,
)
from app.utils.text import format_project_paths, help_text

router = Router()
logger = logging.getLogger(__name__)

SECTION_LABELS = {
    "partition": "partition",
    "smart_sharpness": "smart sharpness",
    "downsample": "downsample",
    "mask_people": "people masks",
    "mask_sky": "sky masks",
    "unite_masks": "unite masks",
    "train": "train",
    "merge": "merge",
}

PROJECT_CONFIG_TOKENS: dict[str, str] = {}


class ConfigEditState(StatesGroup):
    waiting_value = State()


class AdminOnlyFilter(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        if not settings.admins:
            return True
        return bool(event.from_user and event.from_user.id in settings.admins)


router.message.filter(AdminOnlyFilter())
router.callback_query.filter(AdminOnlyFilter())


def extract_raw_arg(command: CommandObject) -> str:
    return (command.args or "").strip()


def split_key_value(raw: str) -> tuple[str, str]:
    parts = raw.split(maxsplit=1)
    if len(parts) != 2:
        raise PipelineDefaultsError("Нужны ключ и значение. Пример: /set partition.grid_dim_x 4")
    return parts[0].strip(), parts[1].strip()


def humanize_name(name: str) -> str:
    return SECTION_LABELS.get(name, name.replace("_", " "))


def format_yaml_scalar(value: object) -> str:
    text = yaml.safe_dump(value, allow_unicode=False, sort_keys=False).strip()
    if text.endswith("\n..."):
        return text[:-4]
    return text


def remember_project_token(windows_path: str) -> str:
    token = secrets.token_hex(6)
    PROJECT_CONFIG_TOKENS[token] = windows_path
    if len(PROJECT_CONFIG_TOKENS) > 256:
        PROJECT_CONFIG_TOKENS.pop(next(iter(PROJECT_CONFIG_TOKENS)))
    return token


def build_project_configs_markup(paths, defaults, token: str | None = None):
    status = get_project_configs_status(paths, defaults.train, defaults.partition)
    token = token or remember_project_token(paths.windows_path)
    builder = InlineKeyboardBuilder()
    if status.exists:
        builder.row(InlineKeyboardButton(text="✅ config", callback_data=f"pcfg:noop:{token}"))
    else:
        builder.row(InlineKeyboardButton(text="create config", callback_data=f"pcfg:create:{token}"))
    return builder.as_markup()


def build_config_menu_keyboard():
    builder = InlineKeyboardBuilder()
    for section, label in SECTION_LABELS.items():
        builder.button(text=label, callback_data=f"cfg:section:{section}")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="reset all", callback_data="cfg:reset:all"))
    return builder.as_markup()


def build_section_keyboard(section: str, waiting_field: str | None = None):
    defaults = load_pipeline_defaults()
    section_obj = getattr(defaults, section)
    builder = InlineKeyboardBuilder()

    for field_info in fields(section_obj):
        field_name = field_info.name
        label = humanize_name(field_name)
        if waiting_field == field_name:
            label = f"[{label}]"
        builder.button(text=label[:48], callback_data=f"cfg:field:{section}:{field_name}")

    builder.adjust(2)
    builder.row(
        InlineKeyboardButton(text="reset section", callback_data=f"cfg:reset:{section}"),
        InlineKeyboardButton(text="back", callback_data="cfg:menu"),
    )
    if waiting_field:
        builder.row(InlineKeyboardButton(text="cancel input", callback_data="cfg:cancel"))
    return builder.as_markup()


def build_config_menu_text() -> str:
    return (
        "Редактор параметров pipeline.\n\n"
        "Нажми секцию, затем параметр, и после этого просто пришли новое значение сообщением.\n"
        "Поддерживаются обычные YAML-значения: <code>320</code>, <code>false</code>, "
        "<code>[0,1,2]</code>, <code>main</code>."
    )


def build_section_text(section: str, waiting_field: str | None = None) -> str:
    defaults = load_pipeline_defaults()
    body = render_pipeline_defaults(defaults, section)
    lines = [
        f"Редактор секции <code>{escape(section)}</code>.",
        "",
        f"<pre>{escape(body)}</pre>",
        "",
    ]
    if waiting_field:
        current_value = getattr(getattr(defaults, section), waiting_field)
        lines.append(
            "Жду новое значение для "
            f"<code>{escape(section)}.{escape(waiting_field)}</code>.\n"
            f"Текущее: <code>{escape(format_yaml_scalar(current_value))}</code>"
        )
    else:
        lines.append("Выбери параметр кнопкой ниже.")
    return "\n".join(lines)


def build_pipeline_message(dataset_path: str, steps: list[tuple[str, str]]) -> str:
    lines = [
        "Готовый pipeline preview:",
        "",
        "# dataset",
        f"<pre>{escape(f'DATASET=\"{dataset_path}\"')}</pre>",
    ]
    for title, cmd in steps:
        lines.extend(["", f"# {escape(title)}", f"<pre>{escape(cmd)}</pre>"])
    return "\n".join(lines)


def build_train_message(commands: list[tuple[str, str]]) -> str:
    lines = ["Готовые train-команды:"]
    for title, cmd in commands:
        lines.extend(["", f"# {escape(title)}", f"<pre>{escape(cmd)}</pre>"])
    return "\n".join(lines)


async def send_html_error(message: Message, text: str) -> None:
    await message.answer(f"Ошибка:\n<code>{escape(text)}</code>", parse_mode="HTML")


async def send_labeled_block(
    message: Message,
    title: str,
    body: str,
    prefix: str | None = None,
    reply_markup=None,
) -> None:
    lines: list[str] = []
    if prefix:
        lines.extend([escape(prefix), ""])
    lines.append(f"# {escape(title)}")
    lines.append(f"<pre>{escape(body)}</pre>")
    await message.answer("\n".join(lines), parse_mode="HTML", reply_markup=reply_markup)


async def edit_callback_message(callback: CallbackQuery, text: str, reply_markup) -> None:
    if callback.message is None:
        await callback.answer()
        return
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=reply_markup)
    except Exception:
        logger.exception("failed to edit callback message")
    await callback.answer()


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Бот для генерации GS pipeline-команд.\n\n" + help_text(),
        parse_mode="HTML",
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(help_text(), parse_mode="HTML")


@router.message(Command("config"))
async def cmd_config(message: Message, command: CommandObject, state: FSMContext) -> None:
    raw = extract_raw_arg(command)
    await state.clear()

    if raw:
        try:
            section = normalize_section_name(raw)
        except PipelineDefaultsError as e:
            await send_html_error(message, str(e))
            return

        await message.answer(
            build_section_text(section),
            parse_mode="HTML",
            reply_markup=build_section_keyboard(section),
        )
        return

    await message.answer(
        build_config_menu_text(),
        parse_mode="HTML",
        reply_markup=build_config_menu_keyboard(),
    )


@router.callback_query(F.data == "cfg:menu")
async def cb_config_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await edit_callback_message(callback, build_config_menu_text(), build_config_menu_keyboard())


@router.callback_query(F.data == "cfg:cancel")
async def cb_config_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    section = data.get("section")
    await state.clear()

    if section:
        await edit_callback_message(callback, build_section_text(section), build_section_keyboard(section))
        return

    await edit_callback_message(callback, build_config_menu_text(), build_config_menu_keyboard())


@router.callback_query(F.data.startswith("cfg:section:"))
async def cb_config_section(callback: CallbackQuery, state: FSMContext) -> None:
    _, _, section = callback.data.split(":", 2)
    await state.clear()
    await edit_callback_message(callback, build_section_text(section), build_section_keyboard(section))


@router.callback_query(F.data.startswith("cfg:field:"))
async def cb_config_field(callback: CallbackQuery, state: FSMContext) -> None:
    _, _, section, field_name = callback.data.split(":", 3)

    await state.set_state(ConfigEditState.waiting_value)
    if callback.message is not None:
        await state.update_data(
            section=section,
            field=field_name,
            menu_chat_id=callback.message.chat.id,
            menu_message_id=callback.message.message_id,
        )
    else:
        await state.update_data(section=section, field=field_name)

    await edit_callback_message(
        callback,
        build_section_text(section, waiting_field=field_name),
        build_section_keyboard(section, waiting_field=field_name),
    )


@router.callback_query(F.data.startswith("cfg:reset:"))
async def cb_config_reset(callback: CallbackQuery, state: FSMContext) -> None:
    _, _, target = callback.data.split(":", 2)
    await state.clear()

    try:
        reset_pipeline_defaults(target)
    except PipelineDefaultsError as e:
        await callback.answer(str(e), show_alert=True)
        return

    if target == "all":
        await edit_callback_message(
            callback,
            "Все секции сброшены к базовому пресету.\n\n" + build_config_menu_text(),
            build_config_menu_keyboard(),
        )
        return

    await edit_callback_message(
        callback,
        f"Секция <code>{escape(target)}</code> сброшена.\n\n" + build_section_text(target),
        build_section_keyboard(target),
    )


@router.callback_query(F.data.startswith("pcfg:noop:"))
async def cb_project_configs_noop(callback: CallbackQuery) -> None:
    await callback.answer("configs уже на месте")


@router.callback_query(F.data.startswith("pcfg:create:"))
async def cb_project_configs_create(callback: CallbackQuery) -> None:
    _, _, token = callback.data.split(":", 2)
    windows_path = PROJECT_CONFIG_TOKENS.get(token)
    if not windows_path:
        await callback.answer("Контекст устарел. Сгенерируй команду заново.", show_alert=True)
        return

    try:
        paths = build_project_paths(windows_path)
        defaults = load_pipeline_defaults()
        status = create_project_configs(paths, defaults.train, defaults.partition)
    except (ProjectConfigsError, PathMappingError, OSError) as e:
        await callback.answer(str(e), show_alert=True)
        return
    except Exception as e:
        logger.exception("project config creation failed")
        await callback.answer(str(e), show_alert=True)
        return

    if callback.message is not None:
        try:
            await callback.message.edit_reply_markup(
                reply_markup=build_project_configs_markup(paths, defaults, token=token)
            )
        except Exception:
            logger.exception("failed to refresh project config button")

    await callback.answer("configs созданы: " + ", ".join(status.expected_files), show_alert=True)


@router.message(ConfigEditState.waiting_value, Command("cancel"))
async def cmd_config_cancel(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    section = data.get("section")
    await state.clear()

    if section:
        await message.answer(
            build_section_text(section),
            parse_mode="HTML",
            reply_markup=build_section_keyboard(section),
        )
        return

    await message.answer(
        build_config_menu_text(),
        parse_mode="HTML",
        reply_markup=build_config_menu_keyboard(),
    )


@router.message(ConfigEditState.waiting_value, F.text)
async def msg_config_value(message: Message, state: FSMContext) -> None:
    raw_value = (message.text or "").strip()
    data = await state.get_data()
    section = data.get("section")
    field_name = data.get("field")

    if not section or not field_name:
        await state.clear()
        await send_html_error(message, "Состояние редактирования потеряно. Открой /config заново.")
        return

    key_path = f"{section}.{field_name}"
    try:
        defaults, _, _ = set_pipeline_default(key_path, raw_value)
        section_body = render_pipeline_defaults(defaults, section)
    except PipelineDefaultsError as e:
        await send_html_error(message, str(e))
        return
    except Exception as e:
        logger.exception("config set failed")
        await send_html_error(message, str(e))
        return

    await state.clear()

    menu_chat_id = data.get("menu_chat_id")
    menu_message_id = data.get("menu_message_id")
    if menu_chat_id and menu_message_id:
        try:
            await message.bot.edit_message_text(
                chat_id=menu_chat_id,
                message_id=menu_message_id,
                text=build_section_text(section),
                parse_mode="HTML",
                reply_markup=build_section_keyboard(section),
            )
        except Exception:
            logger.exception("failed to refresh config editor message")

    await send_labeled_block(
        message,
        title=f"updated: {key_path}",
        body=section_body,
        prefix="Значение сохранено.",
    )


@router.message(Command("set"))
async def cmd_set(message: Message, command: CommandObject, state: FSMContext) -> None:
    raw = extract_raw_arg(command)
    if not raw:
        await message.answer(
            "После /set нужен ключ и значение.\n"
            "Пример: <code>/set partition.grid_dim_x 4</code>",
            parse_mode="HTML",
        )
        return

    try:
        key_path, raw_value = split_key_value(raw)
        defaults, updated_key, _ = set_pipeline_default(key_path, raw_value)
        section = updated_key.split(".", 1)[0]
        body = render_pipeline_defaults(defaults, section)
    except PipelineDefaultsError as e:
        await send_html_error(message, str(e))
        return
    except Exception as e:
        logger.exception("config set failed")
        await send_html_error(message, str(e))
        return

    await state.clear()
    await send_labeled_block(
        message,
        title=f"updated: {updated_key}",
        body=body,
        prefix="Значение сохранено.",
    )


@router.message(Command("reset"))
async def cmd_reset(message: Message, command: CommandObject, state: FSMContext) -> None:
    raw = extract_raw_arg(command)
    if not raw:
        await message.answer(
            "После /reset нужна секция или <code>all</code>.\n"
            "Пример: <code>/reset train</code>",
            parse_mode="HTML",
        )
        return

    try:
        reset_pipeline_defaults(raw)
    except PipelineDefaultsError as e:
        await send_html_error(message, str(e))
        return
    except Exception as e:
        logger.exception("config reset failed")
        await send_html_error(message, str(e))
        return

    await state.clear()
    if raw.strip().lower() == "all":
        await message.answer(
            "Все секции сброшены.\n\n" + build_config_menu_text(),
            parse_mode="HTML",
            reply_markup=build_config_menu_keyboard(),
        )
        return

    section = normalize_section_name(raw)
    await message.answer(
        build_section_text(section),
        parse_mode="HTML",
        reply_markup=build_section_keyboard(section),
    )


@router.message(Command("path"))
async def cmd_path(message: Message, command: CommandObject) -> None:
    raw = extract_raw_arg(command)
    if not raw:
        await message.answer("После /path нужен windows-путь.")
        return

    try:
        paths = build_project_paths(raw)
    except PathMappingError as e:
        await send_html_error(message, str(e))
        return

    await message.answer(format_project_paths(paths), parse_mode="HTML")


@router.message(Command("partition"))
async def cmd_partition(message: Message, command: CommandObject) -> None:
    raw = extract_raw_arg(command)
    if not raw:
        await message.answer("После /partition нужен windows-путь.")
        return

    try:
        paths = build_project_paths(raw)
        defaults = load_pipeline_defaults()
        cmd = build_partition_command(paths, defaults.partition)
    except Exception as e:
        logger.exception("partition build failed")
        await send_html_error(message, str(e))
        return

    await send_labeled_block(message, title="partition", body=cmd, prefix="Команда partition:")


@router.message(Command("train"))
async def cmd_train(message: Message, command: CommandObject) -> None:
    raw = extract_raw_arg(command)
    if not raw:
        await message.answer("После /train нужен windows-путь.")
        return

    try:
        paths = build_project_paths(raw)
        defaults = load_pipeline_defaults()
        commands = [(params.name, build_train_command(params)) for params in resolve_train_params(paths, defaults)]
        train_message = build_train_message(commands)
        configs_markup = build_project_configs_markup(paths, defaults)
    except Exception as e:
        logger.exception("train build failed")
        await send_html_error(message, str(e))
        return

    await message.answer(train_message, parse_mode="HTML", reply_markup=configs_markup)


@router.message(Command("merge"))
async def cmd_merge(message: Message, command: CommandObject) -> None:
    raw = extract_raw_arg(command)
    if not raw:
        await message.answer("После /merge нужен windows-путь.")
        return

    try:
        paths = build_project_paths(raw)
        defaults = load_pipeline_defaults()
        cmd = build_merge_command(build_merge_params(paths, defaults.merge))
    except Exception as e:
        logger.exception("merge build failed")
        await send_html_error(message, str(e))
        return

    await send_labeled_block(message, title="merge", body=cmd, prefix="Команда merge:")


@router.message(Command("pipeline"))
async def cmd_pipeline(message: Message, command: CommandObject) -> None:
    raw = extract_raw_arg(command)
    if not raw:
        await message.answer("После /pipeline нужен windows-путь.")
        return

    try:
        paths = build_project_paths(raw)
        defaults = load_pipeline_defaults()
        steps = build_full_pipeline_steps(paths=paths, defaults=defaults)
        preview = build_pipeline_message(paths.linux_path, steps)
        configs_markup = build_project_configs_markup(paths, defaults)
    except Exception as e:
        logger.exception("pipeline build failed")
        await send_html_error(message, str(e))
        return

    await message.answer(preview, parse_mode="HTML", reply_markup=configs_markup)


@router.message(F.text)
async def raw_path_fallback(message: Message) -> None:
    raw = (message.text or "").strip()

    if not raw:
        return

    if not raw.lower().startswith("x:\\gaussiansplatting\\data\\"):
        await message.answer("Либо пришли windows-путь, либо используй /help.")
        return

    try:
        paths = build_project_paths(raw)
    except Exception as e:
        await send_html_error(message, str(e))
        return

    await message.answer(
        "Распознал путь.\n\n"
        + format_project_paths(paths)
        + "\n\nДля полного набора команд:\n<code>/pipeline "
        + escape(paths.windows_path)
        + "</code>",
        parse_mode="HTML",
    )
