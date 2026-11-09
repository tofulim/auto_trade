import json
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

import holidays
from entity.take_profit import TakeProfit
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import Session, select
from trading_settings import TradingSettingsService

if TYPE_CHECKING:
    from trader import Trader


class TakeProfitService:
    """계좌 전체의 목표 수익률을 확인하고 보유 구간마다 한 번 절반 익절한다."""

    def __init__(self, engine: Engine, trader: "Trader") -> None:
        """기존 DB와 증권사 클라이언트를 사용한다.

        Args:
            engine: 상태를 영속 저장할 SQLite 엔진.
            trader: 잔고 조회와 매도를 수행할 클라이언트.
        """
        self.engine = engine
        self.trader = trader

    def get_states(self) -> list[dict]:
        """접수와 체결 상태를 조회한다.

        Returns:
            종목별 익절 주문 상태.
        """
        with Session(self.engine) as session:
            return [row.dict() for row in session.exec(select(TakeProfit)).all()]

    def run(self) -> dict:
        """장 마감 후 당일 종가를 확인하고 다음 거래일 예약 매도를 접수한다.

        Returns:
            실행 여부와 종목별 주문 상태.

        Raises:
            RuntimeError: 잔고 또는 체결 내역 조회가 실패한 경우.
        """
        now = datetime.now(timezone(timedelta(hours=9)))
        if now.weekday() >= 5 or now.date() in holidays.SouthKorea() or not time(15, 40) <= now.time() < time(23, 40):
            return {"status": "outside_reservation_hours", "orders": []}
        today = now.strftime("%Y%m%d")

        threshold = Decimal(str(TradingSettingsService(self.engine).get()["take_profit_threshold"]))
        balance = self.trader.inquire_balance()
        if balance["status_code"] != "200":
            raise RuntimeError(f"익절 잔고 조회 실패: {balance['error']}")
        holdings = {row["pdno"]: row for row in balance["output"]["output1"]}

        # 체결을 먼저 확인해야 잔고가 0인 종목도 미확정 주문을 지우지 않는다.
        with Session(self.engine) as session:
            session.execute(text("BEGIN IMMEDIATE"))
            for state in session.exec(select(TakeProfit)).all():
                if state.status == "accepted":
                    self._reconcile(state, today)
                    session.add(state)
                quantity = int(holdings.get(state.stock_symbol, {}).get("hldg_qty", "0"))
                if quantity == 0 and state.status in {"completed", "ready"}:
                    session.delete(state)
            session.commit()

        results = []
        for symbol, holding in holdings.items():
            quantity = int(holding["hldg_qty"])
            if quantity <= 0:
                continue
            average = Decimal(holding["pchs_avg_pric"])
            prices = self.trader.inquire_daily_prices(stock_code=symbol)
            if prices["status_code"] != "200":
                raise RuntimeError(f"익절 종가 조회 실패: {symbol}")
            closes = [row for row in prices["output"] if row["stck_bsop_date"] == today]
            if not closes:
                continue
            price = Decimal(closes[0]["stck_clpr"])
            if average <= 0 or (price - average) * 100 < average * threshold:
                continue
            with Session(self.engine) as session:
                session.execute(text("BEGIN IMMEDIATE"))
                state = session.get(TakeProfit, symbol)
                if state is not None and state.status != "ready":
                    continue
                if state is None:
                    if quantity < 2:
                        continue
                    state = TakeProfit(stock_symbol=symbol, target_qty=quantity // 2)
                remaining = state.target_qty - state.filled_qty
                if int(holding["ord_psbl_qty"]) < remaining:
                    continue
                state.status = "pending"
                state.order_qty = remaining
                state.order_date = today
                state.order_number = ""
                session.add(state)
                session.commit()

            # 접수 의도를 먼저 저장하여 응답 유실이나 동시 실행 시 재매도를 차단한다.
            result = self.trader.rsvn_stock(
                stock_code=symbol, ord_qty=remaining, ord_price=0, sll_buy_dvsn_cd="01", ord_dvsn_cd="01"
            )
            with Session(self.engine) as session:
                state = session.get(TakeProfit, symbol)
                state.result = json.dumps(result, ensure_ascii=False)
                if result["status_code"] == "200" and result["output"].get("RSVN_ORD_SEQ"):
                    state.status = "accepted"
                    state.order_number = result["output"]["RSVN_ORD_SEQ"]
                elif result["status_code"] == "4xx":
                    state.status = "ready"
                else:
                    state.status = "unknown"
                session.add(state)
                session.commit()
            results.append({"stock_symbol": symbol, "result": result})
        return {"status": "checked", "orders": results, "states": self.get_states()}

    def _reconcile(self, state: TakeProfit, today: str) -> None:
        """접수 성공과 체결 완료를 구분하고 취소 시 남은 목표 수량을 보존한다.

        Args:
            state: 확인할 익절 주문 기록.
            today: 장 마감 후 검사일 YYYYMMDD.

        Raises:
            RuntimeError: 체결 조회 실패 또는 주문 내역이 불명확한 경우.
        """
        result = self.trader.get_reserved_orders(rsvn_ord_start_dt=state.order_date, rsvn_ord_end_dt=today)
        if result["status_code"] != "200":
            raise RuntimeError(f"익절 체결 조회 실패: {state.stock_symbol}")
        orders = [
            row
            for row in result["output"]
            if row["rsvn_ord_seq"] == state.order_number
            and row["rsvn_ord_rcit_dt"] == state.order_date
            and row["pdno"] == state.stock_symbol
            and row["sll_buy_dvsn_cd"] == "01"
        ]
        if len(orders) != 1:
            raise RuntimeError(f"익절 주문 내역 확인 필요: {state.stock_symbol}")
        order = orders[0]
        filled = int(order["tot_ccld_qty"])
        # 일반예약은 다음 거래일 하루만 유효하므로 처리일 장 마감 뒤 잔량을 재평가한다.
        if (
            filled == state.order_qty
            or order["cncl_ord_dt"]
            or (state.order_date < today and order["prcs_rslt"] == "처리")
        ):
            state.filled_qty += filled
            state.status = "completed" if state.filled_qty >= state.target_qty else "ready"
