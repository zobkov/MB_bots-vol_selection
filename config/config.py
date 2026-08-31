import logging
from datetime import datetime
from typing import Optional, Dict, Any
import os
import json
from environs import Env

logger = logging.getLogger(__name__)

from dataclasses import dataclass, field

@dataclass
class DatabaseConfig:
    user: str
    password: str
    database: str
    host: str
    port: int = 5432

@dataclass
class RedisConfig:
    password: Optional[str]
    host: str = "localhost"
    port: int = 6379

@dataclass
class TgBot:
    token: str

@dataclass
class GoogleConfig:
    credentials_path: str
    spreadsheet_id: str
    drive_folder_id: Optional[str] = None  # Теперь опциональный
    spreadsheet_name: str = "Заявки КБК26"  # Название таблицы по умолчанию
    drive_folder_name: str = "Резюме_КБК26"  # Название папки по умолчанию
    enable_drive: bool = False  # Включить/выключить Google Drive

@dataclass
class SelectionConfig:
    stages: Dict[str, Any]
    support_contacts: Dict[str, str]
    departments: Dict[str, Any] = field(default_factory=dict)
    how_found_options: list[str] = field(default_factory=list)

@dataclass
class Config:
    tg_bot: TgBot
    db: DatabaseConfig
    redis: RedisConfig
    selection: SelectionConfig
    google: Optional[GoogleConfig] = None
    log_level: str = "INFO"

def load_config(path: str = None) -> Config:
    # Загружаем JSON конфигурацию
    config_path = os.path.join(os.path.dirname(__file__), 'selection_config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        json_config = json.load(f)
    
    # Загружаем переменные окружения для секретных данных
    env = Env()
    env.read_env()
    

    tg_bot = TgBot(token=env.str("BOT_TOKEN"))
    db_config = DatabaseConfig(
        user=env.str("DB_USER"),
        password=env.str("DB_PASS"),
        database=env.str("DB_NAME"),
        host=env.str("DB_HOST"),
        port=env.int("DB_PORT", 5432)
    )

    redis = RedisConfig(
        host=env.str("REDIS_HOST", "localhost"),
        port=env.int("REDIS_PORT", 6379),
        password=env.str("REDIS_PASSWORD", None) if env.str("REDIS_PASSWORD", "") else None
    )
    
    # Настройки Google (опциональные)
    google_config = None
    credentials_path = env.str("GOOGLE_CREDENTIALS_PATH", None)
    spreadsheet_id = env.str("GOOGLE_SPREADSHEET_ID", None)
    drive_folder_id = env.str("GOOGLE_DRIVE_FOLDER_ID", None)
    enable_drive = env.bool("GOOGLE_ENABLE_DRIVE", False)  # По умолчанию Drive отключен
    
    logger.info(f"Google credentials check: credentials_path={credentials_path}, spreadsheet_id={spreadsheet_id}")
    logger.info(f"Google Drive settings: drive_folder_id={drive_folder_id}, enable_drive={enable_drive}")
    
    if credentials_path and spreadsheet_id:
        google_config = GoogleConfig(
            credentials_path=credentials_path,
            spreadsheet_id=spreadsheet_id,
            drive_folder_id=drive_folder_id,
            enable_drive=enable_drive
        )
        logger.info(f"Google config создан: {google_config}")
        logger.info(f"Google Drive {'включен' if enable_drive else 'отключен'}")
    else:
        logger.warning("Некоторые переменные Google не заданы, Google сервисы отключены")
    
    selection_config = SelectionConfig(
        stages=json_config.get("selection_stages", {}),
        support_contacts=json_config.get("support_contacts", {}),
        departments=json_config.get("departments", {}),
        how_found_options=json_config.get("how_found_options", [])
    )

    
    log_level = env.str("LOG_LEVEL", "INFO")
    
    return Config(
        tg_bot=tg_bot,
        db=db_config,
        redis=redis,
        selection=selection_config,
        google=google_config,
        log_level=log_level
    )