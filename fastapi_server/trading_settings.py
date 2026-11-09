import os

from entity.trading_settings import TradingSettings
from pydantic import BaseModel, Field, root_validator
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import Session


class TradingSettingsUpdate(BaseModel):
    """생략한 값은 유지하며 퍼센트 기준으로 설정을 변경한다."""

    take_profit_threshold: float = Field(default=None, gt=0, allow_inf_nan=False)
    purchase_threshold: float = Field(default=None, allow_inf_nan=False)
    sell_threshold: float = Field(default=None, allow_inf_nan=False)
    period_days: int = Field(default=None, ge=1, le=365)

    @root_validator(pre=True)
    def reject_null(cls, values: dict) -> dict:
        """명시적인 null은 유효한 설정으로 저장하지 않는다.

        Args:
            values: 전달된 설정값.

        Returns:
            검증을 통과한 입력값.

        Raises:
            ValueError: null 값이 전달된 경우.
        """
        if any(value is None for value in values.values()):
            raise ValueError("설정값에 null을 사용할 수 없습니다.")
        return values

    class Config:
        extra = "forbid"


class TradingSettingsService:
    """공통 매매 설정을 SQLite에서 조회하고 변경한다."""

    def __init__(self, engine: Engine) -> None:
        """설정을 저장할 엔진을 지정한다.

        Args:
            engine: 기존 애플리케이션의 SQLite 엔진.
        """
        self.engine = engine

    def get(self) -> dict:
        """최초 기본값을 저장하고 현재 설정을 반환한다.

        Returns:
            현재 적용되는 매매 설정.
        """
        return self.update(TradingSettingsUpdate())

    def update(self, changes: TradingSettingsUpdate) -> dict:
        """전달된 설정만 원자적으로 변경한다.

        Args:
            changes: 변경할 필드와 값.

        Returns:
            변경 후 전체 설정.
        """
        with Session(self.engine) as session:
            session.execute(text("BEGIN IMMEDIATE"))
            settings = session.get(TradingSettings, 1)
            if settings is None:
                defaults = {
                    field: os.environ[field.upper()]
                    for field in TradingSettingsUpdate.__fields__
                    if field.upper() in os.environ
                }
                validated = TradingSettingsUpdate(**defaults)
                settings = TradingSettings(**validated.dict(exclude_unset=True))
            for field, value in changes.dict(exclude_unset=True).items():
                setattr(settings, field, value)
            session.add(settings)
            session.commit()
            session.refresh(settings)
            return settings.dict(exclude={"id"})
