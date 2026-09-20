from sqlalchemy import select, update, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User, Application, Stage2Application
from typing import Optional, List, Dict, Any
from utils.logging_config import log_db_operation, log_error
from utils.google_services import GoogleSheetsService


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_user(self, telegram_id: int, telegram_username: Optional[str] = None) -> User:
        """Получить или создать пользователя"""
        try:
            result = await self.session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            
            if user is None:
                user = User(
                    telegram_id=telegram_id,
                    telegram_username=telegram_username
                )
                self.session.add(user)
                await self.session.commit()
                await self.session.refresh(user)
                log_db_operation("CREATE", "users", "new user created", telegram_id)
            else:
                if user.telegram_username != telegram_username:
                    user.telegram_username = telegram_username
                    await self.session.commit()
                    log_db_operation("UPDATE", "users", f"username updated to {telegram_username}", telegram_id)
                log_db_operation("SELECT", "users", "existing user found", telegram_id)
            
            return user
        except Exception as e:
            log_error(e, "Ошибка при получении/создании пользователя", telegram_id)
            raise

    async def update_status(self, telegram_id: int, status: str) -> bool:
        """Обновить статус пользователя по telegram_id или id в БД"""
        try:
            result = await self.session.execute(
                update(User)
                .where(User.telegram_id == telegram_id)
                .values(status=status)
            )
            if result.rowcount == 0:
                # Попробуем по внутреннему id
                result = await self.session.execute(
                    update(User)
                    .where(User.id == telegram_id)
                    .values(status=status)
                )
            await self.session.commit()
            log_db_operation("UPDATE", "users", f"status updated to {status}", telegram_id)
            return result.rowcount > 0
        except Exception as e:
            log_error(e, "Ошибка при обновлении статуса пользователя", telegram_id)
            raise

    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Получить пользователя по telegram_id"""
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Получить пользователя по первичному ключу id"""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Получить пользователя по username (без учета регистра и @)"""
        clean_username = username.strip().lstrip('@')
        if not clean_username:
            return None
        result = await self.session.execute(
            select(User).where(func.lower(User.telegram_username) == clean_username.lower())
        )
        return result.scalar_one_or_none()

    async def find_user(self, query: str | int) -> Optional[User]:
        """Универсальный поиск пользователя по telegram_id, id или username"""
        if isinstance(query, int) or (isinstance(query, str) and query.strip().isdigit()):
            uid = int(query)
            user = await self.get_user_by_telegram_id(uid)
            if user:
                return user
            user = await self.get_user_by_id(uid)
            if user:
                return user
        
        query_str = str(query).strip()
        return await self.get_user_by_username(query_str)


class ApplicationRepository:
    def __init__(self, session: AsyncSession, google_sheets_service: Optional[GoogleSheetsService] = None):
        self.session = session
        self.google_sheets_service = google_sheets_service

    async def create_application(self, user_id: int, application_data: Dict[str, Any], user_telegram_data: Optional[Dict[str, Any]] = None) -> Application:
        """Создать заявку и экспортировать в Google Sheets"""
        try:
            application = Application(
                user_id=user_id,
                full_name=application_data['full_name'],
                email_st=application_data['email_st'],
                phone=application_data['phone'],
                faculty=application_data['faculty'],
                course=application_data['course'],
                days_count=application_data['days_count'],
                day_zero_available=application_data['day_zero_available'],
                preferred_role=application_data['preferred_role'],
                motivation=application_data['motivation'],
                volunteer_experience=application_data['volunteer_experience'],
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
                           f"application created: {application.full_name}, {application.email_st}", 
                           telegram_id)
            
            # Сохраняем в Google Sheets если сервис настроен
            if self.google_sheets_service:
                try:
                    sheets_data = {
                        'telegram_id': telegram_id,
                        'telegram_username': telegram_username or "",
                        'full_name': application.full_name,
                        'email_st': application.email_st,
                        'phone': application.phone,
                        'faculty': application.faculty,
                        'course': application.course,
                        'days_count': application.days_count,
                        'day_zero_available': "Да" if application.day_zero_available else "Нет",
                        'preferred_role': application.preferred_role,
                        'motivation': application.motivation,
                        'volunteer_experience': application.volunteer_experience,
                        'created_at': application.created_at.strftime('%Y-%m-%d %H:%M:%S') if application.created_at else "",
                    }
                    
                    if user_telegram_data:
                        sheets_data.update(user_telegram_data)
                    
                    success = await self.google_sheets_service.add_application_to_sheet(sheets_data)
                    if success:
                        log_db_operation("GOOGLE_SHEETS", "applications", 
                                       f"application exported to Google Sheets: {application.full_name}", 
                                       telegram_id)
                    else:
                        log_error(Exception("Google Sheets export failed"), 
                                "Не удалось экспортировать заявку в Google Sheets", 
                                telegram_id)
                        
                except Exception as e:
                    log_error(e, "Ошибка при экспорте заявки в Google Sheets", telegram_id)
            
            return application
        except Exception as e:
            log_error(e, "Ошибка при создании заявки")
            raise

    async def get_user_applications(self, user_id: int) -> List[Application]:
        """Получить все заявки пользователя"""
        result = await self.session.execute(
            select(Application).where(Application.user_id == user_id).order_by(Application.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_latest_application_by_user_id(self, user_id: int) -> Optional[Application]:
        """Получить последнюю поданную заявку пользователя"""
        result = await self.session.execute(
            select(Application).where(Application.user_id == user_id).order_by(Application.created_at.desc())
        )
        return result.scalars().first()

    async def delete_user_applications(self, user_id: int) -> int:
        """Удалить все заявки 1-го этапа пользователя"""
        try:
            result = await self.session.execute(
                delete(Application).where(Application.user_id == user_id)
            )
            await self.session.commit()
            log_db_operation("DELETE", "applications", f"Deleted applications for user_id={user_id}")
            return result.rowcount
        except Exception as e:
            log_error(e, f"Ошибка при удалении заявок 1-го этапа для user_id={user_id}")
            raise


class Stage2Repository:
    def __init__(self, session: AsyncSession, google_sheets_service: Optional[GoogleSheetsService] = None):
        self.session = session
        self.google_sheets_service = google_sheets_service

    async def get_by_user_id(self, user_id: int) -> Optional[Stage2Application]:
        """Получить заявку 2-го этапа по user_id"""
        result = await self.session.execute(
            select(Stage2Application).where(Stage2Application.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def delete_by_user_id(self, user_id: int) -> int:
        """Удалить заявку 2-го этапа пользователя"""
        try:
            result = await self.session.execute(
                delete(Stage2Application).where(Stage2Application.user_id == user_id)
            )
            await self.session.commit()
            log_db_operation("DELETE", "stage2_applications", f"Deleted stage 2 app for user_id={user_id}")
            return result.rowcount
        except Exception as e:
            log_error(e, f"Ошибка при удалении заявки 2-го этапа для user_id={user_id}")
            raise

    async def upsert_application(self, user_id: int, data: Dict[str, Any]) -> Stage2Application:
        """Создать или обновить заявку 2-го этапа"""
        try:
            existing = await self.get_by_user_id(user_id)
            if existing is None:
                app = Stage2Application(
                    user_id=user_id,
                    role_type=data.get('role_type', 'general'),
                    q1_about_mb=data.get('q1_about_mb'),
                    q2_motivation=data.get('q2_motivation'),
                    q3_well_organized=data.get('q3_well_organized'),
                    vq1_file_id=data.get('vq1_file_id'),
                    vq2_file_id=data.get('vq2_file_id'),
                    vq3_file_id=data.get('vq3_file_id'),
                    vq4_file_id=data.get('vq4_file_id'),
                    vq5_file_id=data.get('vq5_file_id'),
                    media_has_equipment=data.get('media_has_equipment'),
                    media_experience=data.get('media_experience'),
                    media_portfolio=data.get('media_portfolio'),
                    is_completed=data.get('is_completed', False),
                    reviewed=data.get('reviewed', False)
                )
                self.session.add(app)
                await self.session.commit()
                await self.session.refresh(app)
                log_db_operation("CREATE", "stage2_applications", f"Stage 2 app created for user_id={user_id}")
                return app
            else:
                for key, val in data.items():
                    if hasattr(existing, key):
                        setattr(existing, key, val)
                await self.session.commit()
                await self.session.refresh(existing)
                log_db_operation("UPDATE", "stage2_applications", f"Stage 2 app updated for user_id={user_id}")
                return existing
        except Exception as e:
            log_error(e, f"Ошибка при сохранении заявки 2-го этапа для user_id={user_id}")
            raise

    async def mark_completed(self, user_id: int) -> bool:
        """Пометить 2-й этап как завершенный (пользователем или по таймауту)"""
        try:
            result = await self.session.execute(
                update(Stage2Application)
                .where(Stage2Application.user_id == user_id)
                .values(is_completed=True)
            )
            await self.session.commit()
            return result.rowcount > 0
        except Exception as e:
            log_error(e, f"Ошибка при установке is_completed для user_id={user_id}")
            raise

    async def count_all(self) -> int:
        """Подсчитать общее количество заявок 2-го этапа"""
        result = await self.session.execute(select(func.count(Stage2Application.id)))
        return result.scalar_one() or 0

    async def list_page(self, page: int, limit: int = 10) -> List[Stage2Application]:
        """Получить страницу заявок 2-го этапа"""
        offset = max(0, page * limit)
        result = await self.session.execute(
            select(Stage2Application)
            .order_by(Stage2Application.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def set_reviewed(self, user_id: int, reviewed: bool) -> bool:
        """Переключить флаг reviewed для заявки"""
        try:
            result = await self.session.execute(
                update(Stage2Application)
                .where(Stage2Application.user_id == user_id)
                .values(reviewed=reviewed)
            )
            await self.session.commit()
            return result.rowcount > 0
        except Exception as e:
            log_error(e, f"Ошибка при обновлении статуса reviewed для user_id={user_id}")
            raise

    async def list_all(self) -> List[Stage2Application]:
        """Получить все заявки 2-го этапа"""
        result = await self.session.execute(
            select(Stage2Application).order_by(Stage2Application.created_at.asc())
        )
        return list(result.scalars().all())

