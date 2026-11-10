import inject
from database.database import Database
from fastapi import APIRouter
from trading_settings import TradingSettingsService, TradingSettingsUpdate

router = APIRouter(prefix="/v1/settings", tags=["Trading settings"])


@router.get("/trading")
def get_trading_settings() -> dict:
    """현재 적용되는 공통 매매 설정을 반환한다.

    Returns:
        익절 및 예측 전략의 공통 설정.
    """
    return TradingSettingsService(inject.instance(Database).engine).get()


@router.put("/trading")
def put_trading_settings(changes: TradingSettingsUpdate) -> dict:
    """전달된 필드만 저장하고 다음 실행부터 적용한다.

    Args:
        changes: 변경할 매매 설정.

    Returns:
        변경 후 전체 설정.
    """
    return TradingSettingsService(inject.instance(Database).engine).update(changes)
