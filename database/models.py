from sqlalchemy import BigInteger, String, Boolean, Text, DateTime, ForeignKey, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    telegram_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_alive: Mapped[bool] = mapped_column(Boolean, default=True)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    stage1_submitted: Mapped[str] = mapped_column(String(20), default='not_submitted')  # 'submitted', 'not_submitted'
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Связи
    applications: Mapped[list["Application"]] = relationship("Application", back_populates="user")
    stage2_answers: Mapped[list["Stage2Answer"]] = relationship("Stage2Answer", back_populates="user")
    department_test_results: Mapped[list["DepartmentTestResult"]] = relationship("DepartmentTestResult", back_populates="user")


class Application(Base):
    __tablename__ = 'applications'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id'), nullable=False)
    
    # Поля анкеты
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    middle_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    course: Mapped[str] = mapped_column(String(50), nullable=False)  # '1_bachelor', '2_bachelor', etc.
    is_from_vsm: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)  # Из ВШМ?
    is_from_spbu: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)  # Из СПбГУ?
    university: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Название ВУЗа и факультет
    dormitory: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)  # Общежитие (только для ВШМ)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    personal_qualities: Mapped[str] = mapped_column(Text, nullable=False)
    motivation: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Оценки отделов (1-5)
    logistics_rating: Mapped[int] = mapped_column(BigInteger, nullable=False)
    marketing_rating: Mapped[int] = mapped_column(BigInteger, nullable=False)
    pr_rating: Mapped[int] = mapped_column(BigInteger, nullable=False)
    program_rating: Mapped[int] = mapped_column(BigInteger, nullable=False)
    partners_rating: Mapped[int] = mapped_column(BigInteger, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Связь с пользователем
    user: Mapped["User"] = relationship("User", back_populates="applications")


class Stage2Answer(Base):
    """Ответы на вопросы второго этапа (общие вопросы)"""
    __tablename__ = 'stage2_answers'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id'), nullable=False)
    
    # Данные участия
    participation_days: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # '2' или '3'
    participation_time: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # 'full', 'morning', 'afternoon'
    
    # Ответы на общие вопросы
    general_q1_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 180 сек
    general_q1_time_taken: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # время в секундах
    
    general_q2_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 30 сек
    general_q2_time_taken: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    general_q3_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 15 сек
    general_q3_time_taken: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    general_q4_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 15 сек
    general_q4_time_taken: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    general_q5_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 90 сек
    general_q5_time_taken: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    general_q6_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 30 сек
    general_q6_time_taken: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Статус прохождения общих вопросов
    general_questions_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    general_questions_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    general_questions_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Связь с пользователем
    user: Mapped["User"] = relationship("User", back_populates="stage2_answers")


class DepartmentTestResult(Base):
    """Результаты тестирования по отделам"""
    __tablename__ = 'department_test_results'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id'), nullable=False)
    
    # Информация о тесте
    department: Mapped[str] = mapped_column(String(50), nullable=False)  # 'logistics', 'program', 'partners', 'pr', 'marketing'
    
    # Статус прохождения
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Связь с пользователем и ответами
    user: Mapped["User"] = relationship("User", back_populates="department_test_results")
    answers: Mapped[list["DepartmentTestAnswer"]] = relationship("DepartmentTestAnswer", back_populates="test_result")


class DepartmentTestAnswer(Base):
    """Ответы на вопросы тестирования по отделам"""
    __tablename__ = 'department_test_answers'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    test_result_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('department_test_results.id'), nullable=False)
    
    # Информация о вопросе
    question_number: Mapped[int] = mapped_column(Integer, nullable=False)  # номер вопроса (1, 2, 3...)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)  # текст вопроса для справки
    
    # Ответ пользователя
    answer_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # ответ пользователя
    time_limit: Mapped[int] = mapped_column(Integer, nullable=False)  # лимит времени в секундах
    time_taken: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # фактическое время в секундах
    is_timeout: Mapped[bool] = mapped_column(Boolean, default=False)  # был ли превышен лимит времени
    
    # Для вопросов с правильными ответами
    correct_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # правильный ответ (если есть)
    is_correct: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)  # правильно ли отвечено
    
    answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Связь с результатом теста
    test_result: Mapped["DepartmentTestResult"] = relationship("DepartmentTestResult", back_populates="answers")
