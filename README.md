# GS Pipeline Tg-Bot

Телеграм-бот для генерации команд пайплайна Gaussian Splatting по windows-based пути проекта.

## Что умеет

- принимает путь вида `X:\GaussianSplatting\data\...`
- автоматически переводит его в linux-вид `fdata2/...`
- строит базовые derived paths
- генерирует команды для:
  - partition
  - train
  - merge
  - полного pipeline preview

## Быстрый старт

```bash
pip install -r requirements.txt
# cp .env.example .env
# впиши BOT_TOKEN в .env
python run.py
```

## Команды

- `/path <windows_path>`
- `/partition <windows_path>`
- `/train <windows_path>`
- `/merge <windows_path>`
- `/pipeline <windows_path>`

## Пример

```text
/pipeline X:\GaussianSplatting\data\RIGs\GoPro\10Cams\20260209\for_GS_Track03
```

## Замечания

- бот сейчас **не запускает** shell-команды, а только **генерирует** их
- доступ можно ограничить через `ADMINS` в `.env`
- пресет лежит в `presets/rig_default.yaml`
