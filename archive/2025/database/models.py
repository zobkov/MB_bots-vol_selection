from sqlalchemy import BigInteger, String, Boolean, Text, DateTime, ForeignKey
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

    # Связь с заявками
    applications: Mapped[list["Application"]] = relationship("Application", back_populates="user")


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
