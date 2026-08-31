from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User, Application
from typing import Optional
from utils.logging_config import log_db_operation, log_error
from utils.google_services import GoogleSheetsService
import re


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_user(self, telegram_id: int, telegram_username: Optional[str] = None) -> User:
        """Получить или создать пользователя"""
        try:
            # Попытаемся найти существующего пользователя
            result = await self.session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            
            if user is None:
                # Создаем нового пользователя
                user = User(
                    telegram_id=telegram_id,
                    telegram_username=telegram_username
                )
                self.session.add(user)
                await self.session.commit()
                await self.session.refresh(user)
                log_db_operation("CREATE", "users", f"new user created", telegram_id)
            else:
                # Обновляем username если изменился
                if user.telegram_username != telegram_username:
                    user.telegram_username = telegram_username
                    await self.session.commit()
                    log_db_operation("UPDATE", "users", f"username updated to {telegram_username}", telegram_id)
                log_db_operation("SELECT", "users", f"existing user found", telegram_id)
            
            return user
        except Exception as e:
            log_error(e, "Ошибка при получении/создании пользователя", telegram_id)
            raise

    async def update_stage1_status(self, telegram_id: int, status: str):
        """Обновить статус первого этапа"""
        try:
            await self.session.execute(
                update(User)
                .where(User.telegram_id == telegram_id)
                .values(stage1_submitted=status)
            )
            await self.session.commit()
            log_db_operation("UPDATE", "users", f"stage1_status updated to {status}", telegram_id)
        except Exception as e:
            log_error(e, "Ошибка при обновлении статуса этапа 1", telegram_id)
            raise

    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Получить пользователя по telegram_id"""
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()


class ApplicationRepository:
    def __init__(self, session: AsyncSession, google_sheets_service: Optional[GoogleSheetsService] = None):
        self.session = session
        self.google_sheets_service = google_sheets_service

    @staticmethod
    def parse_full_name(full_name: str) -> tuple[str, str, Optional[str]]:
        """Разделение ФИО на составные части"""
        parts = full_name.strip().split()
        
        if len(parts) >= 2:
            last_name = parts[0]
            first_name = parts[1]
            middle_name = parts[2] if len(parts) >= 3 else None
            return first_name, last_name, middle_name
        elif len(parts) == 1:
            # Если только одно слово, считаем его именем
            return parts[0], "", None
        else:
            return "", "", None

    async def create_application(self, user_id: int, application_data: dict, user_telegram_data: dict = None) -> Application:
        """Создать заявку"""
        try:
            # Разбираем ФИО
            first_name, last_name, middle_name = self.parse_full_name(application_data['full_name'])
            
            application = Application(
                user_id=user_id,
                full_name=application_data['full_name'],
                first_name=first_name,
                last_name=last_name,
                middle_name=middle_name,
                course=application_data['course'],
                is_from_vsm=application_data.get('is_from_vsm'),
                is_from_spbu=application_data.get('is_from_spbu'),
                university=application_data.get('university'),
                dormitory=application_data['dormitory'],
                email=application_data['email'],
                phone=application_data['phone'],
                personal_qualities=application_data['personal_qualities'],
                motivation=application_data['motivation'],
                logistics_rating=application_data['logistics_rating'],
                marketing_rating=application_data['marketing_rating'],
                pr_rating=application_data['pr_rating'],
                program_rating=application_data['program_rating'],
                partners_rating=application_data['partners_rating'],
            )
            
            self.session.add(application)
            await self.session.commit()
            await self.session.refresh(application)
            
            # Получаем telegram_id пользователя для логирования
            user_result = await self.session.execute(
                select(User.telegram_id, User.telegram_username).where(User.id == user_id)
            )
            user_data = user_result.first()
            telegram_id = user_data.telegram_id if user_data else None
            telegram_username = user_data.telegram_username if user_data else None
            
            log_db_operation("CREATE", "applications", 
                           f"application created: {application_data['full_name']}, {application_data['email']}", 
                           telegram_id)
            
            # Сохраняем в Google Sheets если сервис настроен
            if self.google_sheets_service:
                try:
                    # Подготавливаем данные для Google Sheets
                    sheets_data = {
                        'telegram_id': telegram_id,
                        'telegram_username': telegram_username,
                        'full_name': application.full_name,
                        'first_name': application.first_name,
                        'last_name': application.last_name,
                        'middle_name': application.middle_name,
                        'course': application.course,
                        'is_from_vsm': application.is_from_vsm,
                        'is_from_spbu': application.is_from_spbu,
                        'university': application.university,
                        'dormitory': application.dormitory,
                        'email': application.email,
                        'phone': application.phone,
                        'personal_qualities': application.personal_qualities,
                        'motivation': application.motivation,
                        'logistics_rating': application.logistics_rating,
                        'marketing_rating': application.marketing_rating,
                        'pr_rating': application.pr_rating,
                        'program_rating': application.program_rating,
                        'partners_rating': application.partners_rating,
                        'created_at': application.created_at.isoformat(),
                        'updated_at': application.updated_at.isoformat(),
                    }
                    
                    # Добавляем данные пользователя Telegram если переданы
                    if user_telegram_data:
                        sheets_data.update(user_telegram_data)
                    
                    success = await self.google_sheets_service.add_application_to_sheet(sheets_data)
                    if success:
                        log_db_operation("GOOGLE_SHEETS", "applications", 
                                       f"application exported to Google Sheets: {application_data['full_name']}", 
                                       telegram_id)
                    else:
                        log_error(Exception("Google Sheets export failed"), 
                                "Не удалось экспортировать заявку в Google Sheets", 
                                telegram_id)
                        
                except Exception as e:
                    log_error(e, "Ошибка при экспорте заявки в Google Sheets", telegram_id)
                    # Не прерываем выполнение если Google Sheets недоступен
            
            return application
        except Exception as e:
            log_error(e, "Ошибка при создании заявки")
            raise

    async def get_user_applications(self, user_id: int) -> list[Application]:
        """Получить все заявки пользователя"""
        result = await self.session.execute(
            select(Application).where(Application.user_id == user_id)
        )
        return list(result.scalars().all())
