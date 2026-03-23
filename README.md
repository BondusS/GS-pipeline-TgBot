# GS Pipeline Tg-Bot

Телеграм-бот для генерации команд пайплайна Gaussian Splatting 
по windows-based пути проекта.

## Что умеет

- принимает путь вида `X:\GaussianSplatting\data\...`
- автоматически переводит его в linux-вид `fdata2/...`
- строит базовые **derived paths**
- генерирует команды для **полного pipeline preview**

## Загрузка и подготовка проекта

```bash
cd ~/
git clone https://github.com/BondusS/GS-pipeline-TgBot.git
cd GS-pipeline-TgBot
pip install -r requirements.txt
```

Нужно подготовить `.env` файл
1. Напиши https://t.me/BotFather создай бота и получи **BOT_TOKEN**
2. Напиши https://t.me/userinfobot узнай свой **id** и впиши его в **ADMINS**

Редактировать `.env` можно, например, через **Nano**
```bash
nano .env
```
### Запуск
```bash
python run.py
```

## Команды
Самая нужная:
- `/pipeline <windows_path>`

Остальные:
- `/path <windows_path>`
- `/partition <windows_path>`
- `/train <windows_path>`
- `/merge <windows_path>`

## Пример

```text
/pipeline X:\GaussianSplatting\data\RIGs\GoPro\10Cams\20260209\for_GS_Track03
```

## Замечания

- бот сейчас **не запускает** shell-команды, а только **генерирует** их
- доступ можно ограничить через `ADMINS` в `.env`
- пресет лежит в `presets/rig_default.yaml`

## Подготовка окружения для работы с Spark Lods
```bash
cd ~/
git clone https://git.metasoftpro.ru/WS3D/msp-spark.git
cd msp-spark
apt install npm
curl https://sh.rustup.rs -sSf | sh
sourse $HOME/.cargo/env
npm run build-lod --help
```