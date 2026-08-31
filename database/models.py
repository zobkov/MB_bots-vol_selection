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

