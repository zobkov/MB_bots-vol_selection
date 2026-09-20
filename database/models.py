from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, String, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    telegram_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(50), default='registered')  # 'registered', 'submitted'
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Связь с заявками
    applications: Mapped[list["Application"]] = relationship("Application", back_populates="user", cascade="all, delete-orphan")
    stage2_applications: Mapped[list["Stage2Application"]] = relationship("Stage2Application", back_populates="user", cascade="all, delete-orphan")


class Application(Base):
    __tablename__ = 'applications'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id'), nullable=False)
    
    # 1. ФИО
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # 2. Почта st
    email_st: Mapped[str] = mapped_column(String(255), nullable=False)
    # 3. Номер телефона
    phone: Mapped[str] = mapped_column(String(50), nullable=False)
    # 4. Факультет / направление
    faculty: Mapped[str] = mapped_column(String(255), nullable=False)
    # 5. Курс
    course: Mapped[str] = mapped_column(String(100), nullable=False)
    # 6. Количество дней участия (2 или 3 дня)
    days_count: Mapped[str] = mapped_column(String(50), nullable=False)
    # 7. Помощь в 0-й день (21 октября)
    day_zero_available: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # 8. Желаемая роль (волонтер общего функционала, фотограф, видеограф)
    preferred_role: Mapped[str] = mapped_column(String(100), nullable=False)
    # 9. Мотивация (почему именно ты)
    motivation: Mapped[str] = mapped_column(Text, nullable=False)
    # 10. Опыт волонтерства
    volunteer_experience: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Связь с пользователем
    user: Mapped["User"] = relationship("User", back_populates="applications")


class Stage2Application(Base):
    __tablename__ = 'stage2_applications'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id'), unique=True, nullable=False)
    role_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'general', 'media'

    # Вопросы общего функционала:
    # 1. Что ты знаешь о Конференции «Менеджмент Будущего»?
    q1_about_mb: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 2. Почему ты хочешь стать волонтером именно на МБ?
    q2_motivation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 3. Что делает мероприятие действительно хорошо организованным?
    q3_well_organized: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Видеоинтервью общего функционала (file_id кружочков в Telegram):
    # 1. Заметил проблему и решил без поручения
    vq1_file_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # 2. Пожертвовал личным комфортом ради цели
    vq2_file_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # 3. Приоритезация (руководитель / участник / спикер)
    vq3_file_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # 4. Руководитель принял неправильное решение
    vq4_file_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # 5. Работа с человеком, который не нравился
    vq5_file_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Вопросы фотографов / видеографов:
    # 1. Наличие своего оборудования
    media_has_equipment: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    # 2. Опыт съемки профессиональных мероприятий
    media_experience: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 3. Ссылка на портфолио
    media_portfolio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Статус сдачи и завершения этапа (пользователем или по таймауту)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Статус проверки администратором
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Связь с пользователем
    user: Mapped["User"] = relationship("User", back_populates="stage2_applications")

