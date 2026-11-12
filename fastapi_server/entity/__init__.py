"""
Author: zed.ai
Reviewer:
2024.05.11
"""

# /database 볼륨의 구버전 초기화 코드에서도 모든 테이블이 등록되도록 한다.
from entity.asset import Asset  # noqa: F401
from entity.portfolio import Portfolio  # noqa: F401
from entity.take_profit import TakeProfit  # noqa: F401
from entity.trading_settings import TradingSettings  # noqa: F401
