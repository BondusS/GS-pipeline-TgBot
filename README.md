# GS Pipeline Web UI

Web UI интерфейс для генерации команд пайплайна Gaussian Splatting 
по windows-based пути проекта.

Версия в виде Telegram-бота доступна в более раннем коммите: 
https://github.com/BondusS/GS-pipeline-TgBot/tree/1e307be68f51a2a43d25522b45cda51d9ac911cd

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

### Запуск
```bash
python run.py
```

## Замечания

- сейчас сервис **не запускает** shell-команды, а только **генерирует** их
- пресет лежит в `presets/rig_default.yaml`

## Настройка Swap
```bash
sudo fallocate -l 100G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
swapon --show
free -h
```

## Подготовка окружения для работы с Spark Lods
```bash
cd ~/
git clone https://git.metasoftpro.ru/WS3D/msp-spark.git
cd msp-spark

apt update
apt install -y npm curl build-essential

curl https://sh.rustup.rs -sSf | sh -s -- -y
source $HOME/.cargo/env

rustup update
rustup default stable

rustc --version
cargo --version

cd rust
cargo build
cd ..
npm run build-lod --help
```