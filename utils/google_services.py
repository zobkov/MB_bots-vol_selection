import os
import gspread
from google.oauth2.service_account import Credentials
from typing import Optional, Dict, Any
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class GoogleSheetsService:
    """Класс для работы с Google Sheets"""
    
    def __init__(self, credentials_path: str, spreadsheet_id: str):
        """
        Инициализация сервиса Google Sheets
        
        Args:
            credentials_path: Путь к файлу с учетными данными сервисного аккаунта
            spreadsheet_id: ID Google Таблицы
        """
        self.credentials_path = credentials_path
        self.spreadsheet_id = spreadsheet_id
        
        # Области доступа
        self.scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
        ]
        
        self._setup_service()
    
    def _setup_service(self):
        """Настройка сервиса Google Sheets"""
        try:
            # Создаем учетные данные
            credentials = Credentials.from_service_account_file(
                self.credentials_path, 
                scopes=self.scopes
            )
            
            # Настраиваем gspread для работы с Google Sheets
            self.gc = gspread.authorize(credentials)
            logger.info("✅ Google Sheets API настроен")
            
        except Exception as e:
            logger.error(f"Ошибка настройки Google Sheets: {e}")
            raise
    
    async def add_application_to_sheet(self, application_data: Dict[str, Any]) -> bool:
        """
        Добавляет данные заявки в Google Таблицу
        
        Args:
            application_data: Словарь с данными заявки
            
        Returns:
            bool: True если успешно, False в случае ошибки
        """
        try:
            logger.info(f"📊 Начинаем добавление заявки в Google Sheets...")
            logger.info(f"👤 Пользователь: {application_data.get('telegram_id')} (@{application_data.get('telegram_username')})")
            
            # Открываем таблицу по ID
            logger.info(f"📋 Открываем таблицу: {self.spreadsheet_id}")
            spreadsheet = self.gc.open_by_key(self.spreadsheet_id)
            
            worksheet_name = "VOLUNTEERS_2026"
            headers = [
                'Timestamp',
                'User ID',
                'Username',
                '1. ФИО',
                '2. Почта st',
                '3. Телефон',
                '4. Факультет/направление',
                '5. Курс',
                '6. Количество дней',
                '7. 0-й день (21 октября)',
                '8. Роль',
                '9. Мотивация',
                '10. Опыт волонтерства',
                'Created At'
            ]
            
            try:
                logger.info(f"🔍 Ищем лист: {worksheet_name}")
                worksheet = spreadsheet.worksheet(worksheet_name)
                logger.info(f"✅ Лист {worksheet_name} найден")
            except gspread.WorksheetNotFound:
                logger.info(f"📄 Лист {worksheet_name} не найден, создаем новый...")
                worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows=1000, cols=20)
                worksheet.append_row(headers)
                logger.info(f"✅ Лист {worksheet_name} создан с заголовками")
            
            # Проверяем, есть ли уже запись для этого пользователя
            try:
                all_records = worksheet.get_all_records()
                user_id = str(application_data.get('telegram_id'))
                
                existing_row = None
                for i, record in enumerate(all_records, start=2):  # start=2 because row 1 is headers
                    if str(record.get('User ID')) == user_id:
                        existing_row = i
                        break
                
                if existing_row:
                    logger.info(f"🔄 Обновляем существующую запись в строке {existing_row}")
                    update_method = "update"
                else:
                    logger.info(f"➕ Добавляем новую запись")
                    update_method = "insert"
                    
            except Exception as e:
                logger.warning(f"⚠️ Не удалось проверить существующие записи: {e}")
                update_method = "insert"
            
            # Подготавливаем данные для записи
            logger.info(f"📝 Подготавливаем данные для записи...")
            
            row_data = [
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                str(application_data.get('telegram_id', '')),
                str(application_data.get('telegram_username', '')),
                str(application_data.get('full_name', '')),
                str(application_data.get('email_st', '')),
                str(application_data.get('phone', '')),
                str(application_data.get('faculty', '')),
                str(application_data.get('course', '')),
                str(application_data.get('days_count', '')),
                str(application_data.get('day_zero_available', '')),
                str(application_data.get('preferred_role', '')),
                str(application_data.get('motivation', '')),
                str(application_data.get('volunteer_experience', '')),
                str(application_data.get('created_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))),
            ]
            
            logger.info(f"📤 Отправляем данные в Google Sheets...")
            
            if update_method == "update" and existing_row:
                worksheet.update(f'A{existing_row}:N{existing_row}', [row_data])
                logger.info(f"🔄 Заявка пользователя {application_data.get('telegram_id')} обновлена в Google Sheets")
            else:
                worksheet.append_row(row_data)
                logger.info(f"➕ Заявка пользователя {application_data.get('telegram_id')} добавлена в Google Sheets")
            
            logger.info(f"🎉 Заявка пользователя {application_data.get('telegram_id')} успешно сохранена в Google Sheets")
            return True

            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Ошибка добавления заявки в Google Sheets: {e}")
            
            # Детальная диагностика ошибок Google Sheets
            if "quotaExceeded" in error_msg:
                logger.error("📊 ОШИБКА: Превышены лимиты Google Sheets API")
                logger.error("💡 РЕШЕНИЕ: Подождите и повторите попытку позже")
            elif "403" in error_msg:
                if "Forbidden" in error_msg:
                    logger.error("🚫 ОШИБКА: Нет доступа к Google Sheets (403 Forbidden)")
                    logger.error("💡 РЕШЕНИЕ: Проверьте права доступа Service Account к таблице")
                else:
                    logger.error("🚫 ОШИБКА 403: Доступ запрещен")
            elif "401" in error_msg:
                logger.error("🔐 ОШИБКА: Ошибка авторизации Google Sheets (401)")
                logger.error("💡 РЕШЕНИЕ: Проверьте учетные данные Service Account")
            elif "404" in error_msg:
                logger.error("📋 ОШИБКА: Таблица Google Sheets не найдена (404)")
                logger.error(f"💡 РЕШЕНИЕ: Проверьте ID таблицы: {self.spreadsheet_id}")
            elif "500" in error_msg:
                logger.error("🔧 ОШИБКА: Внутренняя ошибка сервера Google (500)")
                logger.error("💡 РЕШЕНИЕ: Повторите попытку позже")
            elif "PERMISSION_DENIED" in error_msg:
                logger.error("🔒 ОШИБКА: Нет прав доступа к таблице")
                logger.error("💡 РЕШЕНИЕ: Предоставьте Service Account доступ к таблице")
            else:
                logger.error(f"❓ НЕИЗВЕСТНАЯ ОШИБКА Google Sheets: {error_msg}")
                
            return False


def setup_google_sheets_service(config) -> Optional[GoogleSheetsService]:
    """
    Настройка Google Sheets сервиса
    
    Args:
        config: Конфигурация приложения
        
    Returns:
        GoogleSheetsService или None в случае ошибки
    """
    try:
        if not config.google:
            logger.warning("Google Sheets не настроен в конфигурации")
            return None
        
        # Проверяем существование файла учетных данных
        if not os.path.exists(config.google.credentials_path):
            logger.warning(f"Файл учетных данных Google не найден: {config.google.credentials_path}")
            return None
        
        return GoogleSheetsService(
            credentials_path=config.google.credentials_path,
            spreadsheet_id=config.google.spreadsheet_id
        )
        
    except Exception as e:
        logger.error(f"Ошибка настройки Google Sheets сервиса: {e}")
        return None
