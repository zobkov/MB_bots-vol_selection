from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User, Application, Stage2Answer, DepartmentTestResult, DepartmentTestAnswer
from typing import Optional, List
from utils.logging_config import log_db_operation, log_error
from utils.google_services import GoogleSheetsService
from datetime import datetime
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


class Stage2Repository:
    """Репозиторий для работы с данными второго этапа (общие вопросы)"""
    
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_stage2_record(self, user_id: int) -> Stage2Answer:
        """Получить или создать запись для второго этапа"""
        try:
            result = await self.session.execute(
                select(Stage2Answer).where(Stage2Answer.user_id == user_id)
            )
            stage2_record = result.scalar_one_or_none()
            
            if stage2_record is None:
                stage2_record = Stage2Answer(user_id=user_id)
                self.session.add(stage2_record)
                await self.session.commit()
                await self.session.refresh(stage2_record)
                log_db_operation("CREATE", "stage2_answers", "new stage2 record created", user_id)
            
            return stage2_record
        except Exception as e:
            log_error(e, "Ошибка при получении/создании записи stage2", user_id)
            raise

    async def update_participation_data(self, user_id: int, days: str, time: str):
        """Обновить данные участия"""
        try:
            await self.session.execute(
                update(Stage2Answer)
                .where(Stage2Answer.user_id == user_id)
                .values(participation_days=days, participation_time=time)
            )
            await self.session.commit()
            log_db_operation("UPDATE", "stage2_answers", f"participation updated: {days} days, {time}", user_id)
        except Exception as e:
            log_error(e, "Ошибка при обновлении данных участия", user_id)
            raise

    async def save_general_answer(self, user_id: int, question_num: int, answer: str, time_taken: int):
        """Сохранить ответ на общий вопрос"""
        try:
            update_data = {
                f'general_q{question_num}_answer': answer,
                f'general_q{question_num}_time_taken': time_taken
            }
            
            await self.session.execute(
                update(Stage2Answer)
                .where(Stage2Answer.user_id == user_id)
                .values(**update_data)
            )
            await self.session.commit()
            log_db_operation("UPDATE", "stage2_answers", f"general question {question_num} answered", user_id)
        except Exception as e:
            log_error(e, f"Ошибка при сохранении ответа на вопрос {question_num}", user_id)
            raise

    async def mark_general_questions_started(self, user_id: int):
        """Отметить начало прохождения общих вопросов"""
        try:
            await self.session.execute(
                update(Stage2Answer)
                .where(Stage2Answer.user_id == user_id)
                .values(general_questions_started_at=datetime.now())
            )
            await self.session.commit()
            log_db_operation("UPDATE", "stage2_answers", "general questions started", user_id)
        except Exception as e:
            log_error(e, "Ошибка при отметке начала общих вопросов", user_id)
            raise

    async def mark_general_questions_completed(self, user_id: int):
        """Отметить завершение общих вопросов"""
        try:
            await self.session.execute(
                update(Stage2Answer)
                .where(Stage2Answer.user_id == user_id)
                .values(
                    general_questions_completed=True,
                    general_questions_completed_at=datetime.now()
                )
            )
            await self.session.commit()
            log_db_operation("UPDATE", "stage2_answers", "general questions completed", user_id)
        except Exception as e:
            log_error(e, "Ошибка при отметке завершения общих вопросов", user_id)
            raise

    async def get_stage2_progress(self, user_id: int) -> Optional[Stage2Answer]:
        """Получить прогресс прохождения второго этапа"""
        result = await self.session.execute(
            select(Stage2Answer).where(Stage2Answer.user_id == user_id)
        )
        return result.scalar_one_or_none()


class DepartmentTestRepository:
    """Репозиторий для работы с тестированием по отделам"""
    
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_test_result(self, user_id: int, department: str) -> DepartmentTestResult:
        """Получить или создать результат теста для отдела"""
        try:
            result = await self.session.execute(
                select(DepartmentTestResult).where(
                    DepartmentTestResult.user_id == user_id,
                    DepartmentTestResult.department == department
                )
            )
            test_result = result.scalar_one_or_none()
            
            if test_result is None:
                test_result = DepartmentTestResult(
                    user_id=user_id,
                    department=department
                )
                self.session.add(test_result)
                await self.session.commit()
                await self.session.refresh(test_result)
                log_db_operation("CREATE", "department_test_results", f"test result created for {department}", user_id)
            
            return test_result
        except Exception as e:
            log_error(e, f"Ошибка при получении/создании результата теста для {department}", user_id)
            raise

    async def start_test(self, user_id: int, department: str):
        """Отметить начало тестирования отдела"""
        try:
            await self.session.execute(
                update(DepartmentTestResult)
                .where(
                    DepartmentTestResult.user_id == user_id,
                    DepartmentTestResult.department == department
                )
                .values(started_at=datetime.now())
            )
            await self.session.commit()
            log_db_operation("UPDATE", "department_test_results", f"test started for {department}", user_id)
        except Exception as e:
            log_error(e, f"Ошибка при отметке начала теста {department}", user_id)
            raise

    async def complete_test(self, user_id: int, department: str):
        """Отметить завершение тестирования отдела"""
        try:
            await self.session.execute(
                update(DepartmentTestResult)
                .where(
                    DepartmentTestResult.user_id == user_id,
                    DepartmentTestResult.department == department
                )
                .values(
                    is_completed=True,
                    completed_at=datetime.now()
                )
            )
            await self.session.commit()
            log_db_operation("UPDATE", "department_test_results", f"test completed for {department}", user_id)
        except Exception as e:
            log_error(e, f"Ошибка при отметке завершения теста {department}", user_id)
            raise

    async def save_answer(self, test_result_id: int, question_number: int, question_text: str, 
                         answer_text: str, time_limit: int, time_taken: int, 
                         is_timeout: bool = False, correct_answer: str = None, 
                         is_correct: bool = None) -> DepartmentTestAnswer:
        """Сохранить ответ на вопрос теста отдела"""
        try:
            answer = DepartmentTestAnswer(
                test_result_id=test_result_id,
                question_number=question_number,
                question_text=question_text,
                answer_text=answer_text,
                time_limit=time_limit,
                time_taken=time_taken,
                is_timeout=is_timeout,
                correct_answer=correct_answer,
                is_correct=is_correct,
                answered_at=datetime.now()
            )
            
            self.session.add(answer)
            await self.session.commit()
            await self.session.refresh(answer)
            
            log_db_operation("CREATE", "department_test_answers", 
                           f"answer saved for question {question_number}", test_result_id)
            return answer
        except Exception as e:
            log_error(e, f"Ошибка при сохранении ответа на вопрос {question_number}")
            raise

    async def get_user_department_tests(self, user_id: int) -> List[DepartmentTestResult]:
        """Получить все результаты тестов пользователя"""
        result = await self.session.execute(
            select(DepartmentTestResult).where(DepartmentTestResult.user_id == user_id)
        )
        return list(result.scalars().all())

    async def get_test_with_answers(self, user_id: int, department: str) -> Optional[DepartmentTestResult]:
        """Получить результат теста с ответами"""
        result = await self.session.execute(
            select(DepartmentTestResult)
            .where(
                DepartmentTestResult.user_id == user_id,
                DepartmentTestResult.department == department
            )
        )
        test_result = result.scalar_one_or_none()
        
        if test_result:
            # Загружаем ответы
            answers_result = await self.session.execute(
                select(DepartmentTestAnswer)
                .where(DepartmentTestAnswer.test_result_id == test_result.id)
                .order_by(DepartmentTestAnswer.question_number)
            )
            test_result.answers = list(answers_result.scalars().all())
        
        return test_result

    async def is_department_completed(self, user_id: int, department: str) -> bool:
        """Проверить, завершен ли тест по отделу"""
        result = await self.session.execute(
            select(DepartmentTestResult.is_completed)
            .where(
                DepartmentTestResult.user_id == user_id,
                DepartmentTestResult.department == department
            )
        )
        completed = result.scalar_one_or_none()
        return completed is True
