import json
import os

import requests


class Trader:
    """
    한국투자증권의 트레이딩 API를 통해 매매하기 위해 필요한 method들이 포함된 클래스이다.
    인증 / 매입 / 매각 을 목적으로 한다.
    """

    def __init__(self, app_key: str, app_secret: str, url_base: str, mode: str):
        """
        거래 API 초기화

        Args:
            app_key (str): APP KEY
            app_secret (str): APP_SECRET
            url_base (str): 한투 api base url 실제/모의 투자 포트는 별도로 설정해야함
            mode (str): 실전투자 | 모의투자 여부 (PROD | DEV)
        """
        print(f"this is {mode} mode trader ...\n")
        self.port = os.getenv("PORT")
        self.app_key = app_key
        self.app_secret = app_secret

        self.url_base = url_base

        self.headers = {"content-type": "application/json"}
        self.access_token = os.getenv("KIS_ACCESS_TOKEN", None)

    def get_credential_access_token(self):
        """
        get method로 호출하는 API 요청에 필요한 access token을 받아온다.

        Returns:
            status_code (int): 200

        """
        api = "oauth2/tokenP"
        body = {"grant_type": "client_credentials", "appkey": self.app_key, "appsecret": self.app_secret}

        try:
            response = requests.post(
                url=f"{self.url_base}:{self.port}/{api}", headers=self.headers, data=json.dumps(body)
            )
            if response.status_code != 200:
                raise Exception("Failed to get access token it was already generated.")
            else:
                self.access_token = response.json()["access_token"]
        except Exception:
            return self.access_token

        return self.access_token

    def hashkey(self, datas: dict):
        """
        post 요청을 안전하게 암호화하여 통신하기 위해 hashkey를 활용한다.

        Args:
            datas (dict): 전달하고자 하는 data

        Returns:
            hashkey (str)

        """
        api = "uapi/hashkey"
        headers = {"content-Type": "application/json", "appKey": self.app_key, "appSecret": self.app_secret}
        port = self.port

        response = requests.post(url=f"{self.url_base}:{port}/{api}", headers=headers, data=json.dumps(datas))
        hashkey = response.json()["HASH"]

        return hashkey

    # 이미 token을 발급받은 경우 토큰을 해당 토큰으로 설정한다.
    def set_credential_access_token(self, access_token: str):
        self.access_token = access_token
        os.environ["KIS_ACCESS_TOKEN"] = access_token

    def rsvn_stock(self, stock_code: str, ord_qty: int, ord_price: int, rsvn_ord_end_dt: str = ""):
        """
        장전 시간외 매수를 통해 전날 종가 기준으로 예약 구매한다.
        해당 stock의 accum asset이 감당할 수 있을만큼 구매한다.
        status_code와 에러를 반환한다.

        Args:
            stock_code (str): 종목코드
            ord_qty (int): 주문 개수
            ord_price (int): 주문 가격
            rsvn_ord_end_dt (str): 예약주문종료일자

        Returns:
            status_code (str): 상태 코드, (200 | 4xx | 5xx)
            output (dict): 주문 결과 KRX_FWDG_ORD_ORGNO(한국거래소 전송주문조직번호), ORNO(주문번호), ORD_TMD(주문시간)을 갖는다.
            error (str): 에러

        """
        tr_id = os.getenv("RSVN_BUY_TR_ID")
        api = "uapi/domestic-stock/v1/trading/order-resv"

        data = {
            # 계좌번호
            "CANO": os.getenv("ACCOUNT_FRONT"),
            "ACNT_PRDT_CD": os.getenv("ACCOUNT_REAR"),
            # 종목번호
            "PDNO": stock_code,
            # 주문구분 - 지정가(00), 시장가(01), 장전 시간외(05)
            "ORD_DVSN_CD": "00",
            # 주문 수량
            "ORD_QTY": str(ord_qty),
            # 주문 단가
            "ORD_UNPR": str(ord_price),
            # 매도 매수 구분 코드 (01: 매도 / 02: 매수)
            "SLL_BUY_DVSN_CD": "02",
            # 주문대상 잔고 구분코드 10: 현금
            "ORD_OBJT_CBLC_DVSN_CD": "10",
        }

        # 예약주문종료일자 (미기입시 다음날 주문처리되고 예약주문은 종료됨)
        if len(rsvn_ord_end_dt) != 0:
            data["RSVN_ORD_END_DT"] = rsvn_ord_end_dt

        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {self.access_token}",
            "appKey": self.app_key,
            "appSecret": self.app_secret,
            "tr_id": tr_id,
            # 개인
            "custtype": "P",
            "hashkey": self.hashkey(data),
        }

        return self._request(api, data, headers)

    def buy_stock(self, stock_code: str, ord_qty: int, ord_price: int, rsvn_ord_end_dt: str = ""):
        """
        지정가 매수.
        status_code와 에러를 반환한다.

        Args:
            stock_code (str): 종목코드
            ord_qty (int): 주문 개수
            ord_price (int): 주문 가격
            rsvn_ord_end_dt (str): 예약주문종료일자

        Returns:
            status_code (str): 상태 코드, (200 | 4xx | 5xx)
            output (dict): 주문 결과 KRX_FWDG_ORD_ORGNO(한국거래소 전송주문조직번호), ORNO(주문번호), ORD_TMD(주문시간)을 갖는다.
            error (str): 에러

        """
        tr_id = os.getenv("BUY_TR_ID")
        api = "uapi/domestic-stock/v1/trading/order-cash"

        data = {
            # 계좌번호
            "CANO": os.getenv("ACCOUNT_FRONT"),
            "ACNT_PRDT_CD": os.getenv("ACCOUNT_REAR"),
            # 종목번호
            "PDNO": stock_code,
            # 주문구분 - 지정가(00), 시장가(01), 장전 시간외(05)
            "ORD_DVSN": "00",
            # 주문 수량
            "ORD_QTY": str(ord_qty),
            # 주문 단가
            "ORD_UNPR": str(ord_price),
        }

        # 예약주문종료일자 (미기입시 다음날 주문처리되고 예약주문은 종료됨)
        if len(rsvn_ord_end_dt) != 0:
            data["RSVN_ORD_END_DT"] = rsvn_ord_end_dt

        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {self.access_token}",
            "appKey": self.app_key,
            "appSecret": self.app_secret,
            "tr_id": tr_id,
            # 개인
            "custtype": "P",
            "hashkey": self.hashkey(data),
        }

        return self._request(api, data, headers)

    def sell_stock(self, stock_code: str, ord_qty: int, ord_price: int):
        """
        지정가 매도.
        status_code와 에러를 반환한다.

        Args:
            stock_code (str): 종목코드
            ord_qty (int): 주문 개수
            ord_price (int): 주문 가격

        Returns:
            status_code (str): 상태 코드, (200 | 4xx | 5xx)
            output (dict): 주문 결과 KRX_FWDG_ORD_ORGNO(한국거래소 전송주문조직번호), ORNO(주문번호), ORD_TMD(주문시간)을 갖는다.
            error (str): 에러

        """
        tr_id = os.getenv("SELL_TR_ID")
        api = "uapi/domestic-stock/v1/trading/order-cash"

        data = {
            # 계좌번호
            "CANO": os.getenv("ACCOUNT_FRONT"),
            "ACNT_PRDT_CD": os.getenv("ACCOUNT_REAR"),
            # 종목번호
            "PDNO": stock_code,
            # 주문구분 - 지정가(00), 시장가(01), 장전 시간외(05)
            "ORD_DVSN": "00",
            # 주문 수량
            "ORD_QTY": str(ord_qty),
            # 주문 단가
            "ORD_UNPR": str(ord_price),
        }

        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {self.access_token}",
            "appKey": self.app_key,
            "appSecret": self.app_secret,
            "tr_id": tr_id,
            # 개인
            "custtype": "P",
            "hashkey": self.hashkey(data),
        }

        return self._request(api, data, headers)

    def _request(self, api: str, data: dict, headers: dict, method: str = "POST"):
        status_code, output, error = "500", {}, None
        # 클라이언트 에러 핸들링 (파라미터 오기입, 장미운영날 주문 등)
        try:
            if method == "POST":
                response = requests.post(
                    url=f"{self.url_base}:{self.port}/{api}", headers=headers, data=json.dumps(data)
                )
            # GET
            else:
                response = requests.get(url=f"{self.url_base}:{self.port}/{api}", headers=headers, params=data)

            status_code = str(response.status_code)
            response_json = response.json()

            # 0 이외의 값은 실패이다.
            if response_json["rt_cd"] != "0":
                status_code = "4xx"
                error = f"{response_json['msg_cd']}: {response_json['msg1']}"
            else:
                output = response_json.get("output", None)
                if output is None:
                    output = response_json
        # 서버 에러 핸들링 (토큰 만료 등)
        except Exception as e:
            status_code = "5xx"
            error = str(e)

        return {"status_code": status_code, "output": output, "error": error}

    def cancel_request(self, ord_orgno: str, orgn_odno: str, method_code: str = "02", fix_price: str = "0"):
        """
        주문당시의 영업점코드와 주문번호를 활용해 요청한 매입/매도 주문을 정정 혹은 취소한다.
        status_code와 에러를 반환한다.

        잔량 전부 주문 여부는 항상 Y로 설정해 전량 취소 혹은 정정하도록 한다. 부분 정정/취소는 미고려

        Args:
            ord_orgno (str): 한국거래소전송주문조직번호
            orgn_odno (str): 원주문번호
            method_code (str): 정정취소 구분코드 (01: 정정, 02: 취소)
            fix_price (str): 정정 단가 (method_code가 01일 때만 유효)

        Returns:
            status_code (str): 상태 코드, (200 | 4xx | 5xx)
            error (str): 에러

        """
        tr_id = os.getenv("CANCEL_FIX_TR_ID")
        api = "uapi/domestic-stock/v1/trading/order-rvsecncl"

        data = {
            # 계좌번호
            "CANO": os.getenv("ACCOUNT_FRONT"),
            "ACNT_PRDT_CD": os.getenv("ACCOUNT_REAR"),
            # 한국거래소전송주문조직번호
            "KRX_FWDG_ORD_ORGNO": ord_orgno,
            # 주문번호
            "ORGN_ODNO": orgn_odno,
            # 주문구분 - 지정가(00), 시장가(01)
            "ORD_DVSN": "00",
            # 정정취소 구분코드 (01: 정정, 02: 취소)
            "RVSE_CNCL_DVSN_CD": method_code,
            # 주문 수량 (0은 전량)
            "ORD_QTY": "0",
            # 주문 단가
            "ORD_UNPR": str(fix_price) if method_code == "01" else "0",
            # 잔량전부주문여부
            "QTY_ALL_ORD_YN": "Y",
        }

        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {self.access_token}",
            "appKey": self.app_key,
            "appSecret": self.app_secret,
            "tr_id": tr_id,
            # 개인
            "custtype": "P",
            "hashkey": self.hashkey(data),
        }

        return self._request(api, data, headers)

    def cancel_rsvn_request(self, rsvn_ord_seq: str):
        """
        주문당시의 영업점코드와 주문번호를 활용해 요청한 매입/매도 예약 주문을 취소한다.
        status_code와 에러를 반환한다.

        Args:
            rsvn_ord_seq (str): 예약주문순번

        Returns:
            status_code (str): 상태 코드, (200 | 4xx | 5xx)
            error (str): 에러

        """
        tr_id = os.getenv("RSVN_CANCEL_TR_ID")
        api = "uapi/domestic-stock/v1/trading/order-resv-rvsecncl"

        data = {
            # 계좌번호
            "CANO": os.getenv("ACCOUNT_FRONT"),
            "ACNT_PRDT_CD": os.getenv("ACCOUNT_REAR"),
            # 예약주문순번
            "RSVN_ORD_SEQ": rsvn_ord_seq,
        }

        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {self.access_token}",
            "appKey": self.app_key,
            "appSecret": self.app_secret,
            "tr_id": tr_id,
            # 개인
            "custtype": "P",
            "hashkey": self.hashkey(data),
        }

        return self._request(api, data, headers)

    def inquire_balance(self):
        """
        주식 잔고조회
        예수금 잔액을 확인하거나 주식 수익을 확인할 수 있다.

        Returns:
            status_code (str): 상태 코드, (200 | 4xx | 5xx)
            output (dict): 주문 결과 KRX_FWDG_ORD_ORGNO(한국거래소 전송주문조직번호), ORNO(주문번호), ORD_TMD(주문시간)을 갖는다.
            error (str): 에러

        """
        tr_id = os.getenv("INQ_BAL_TR_ID")
        api = "uapi/domestic-stock/v1/trading/inquire-balance"

        data = {
            # 계좌번호
            "CANO": os.getenv("ACCOUNT_FRONT"),
            "ACNT_PRDT_CD": os.getenv("ACCOUNT_REAR"),
            # 시간외단일가여부
            "AFHR_FLPR_YN": "N",
            # 오프라인여부
            "OFL_YN": "",
            # 조회 구분
            "INQR_DVSN": "02",
            # 단가 구분
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            # 전일 매매 포함 여부
            "PRCS_DVSN": "00",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        }

        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {self.access_token}",
            "appKey": self.app_key,
            "appSecret": self.app_secret,
            "tr_id": tr_id,
            # 개인
            "custtype": "P",
            "hashkey": self.hashkey(data),
        }

        return self._request(api, data, headers, method="GET")

    def inquire_psbl_rvsecncl(self, inqr_dvsn_1: str, inqr_dvsn_2: str):
        """
        정정/취소 가능 여부 조회
        주문당시의 영업점코드와 주문번호를 활용해 요청한 매입/매도 주문의 정정/취소 가능 여부를 조회한다.

        Args:
            inqr_dvsn_1 (str): 조회구분1 (0 주문 / 1 종목)
            inqr_dvsn_2 (str): 조회구분2 (0 모두 / 1 매도 / 2 매수)

        Returns:
            status_code (str): 상태 코드, (200 | 4xx | 5xx)
            output (dict): 다음 주문 결과 dict를 list로 갖는다.
                ord_gno_brno: str    #주문채번지점번호
                odno: str    #주문번호
                orgn_odno: str    #원주문번호
                ord_dvsn_name: str    #주문구분명
                pdno: str    #상품번호
                prdt_name: str    #상품명
                rvse_cncl_dvsn_name: str    #정정취소구분명
                ord_qty: str    #주문수량
                ord_unpr: str    #주문단가
                ord_tmd: str    #주문시각
                tot_ccld_qty: str    #총체결수량
                tot_ccld_amt: str    #총체결금액
                psbl_qty: str    #가능수량
                sll_buy_dvsn_cd: str    #매도매수구분코드
                ord_dvsn_cd: str    #주문구분코드
                mgco_aptm_odno: str    #운용사지정주문번호
                excg_dvsn_cd: str    #거래소구분코드
                excg_id_dvsn_cd: str    #거래소ID구분코드
                excg_id_dvsn_name: str    #거래소ID구분명
                stpm_cndt_pric: str    #스톱지정가조건가격
                stpm_efct_occr_yn: str    #스톱지정가효력발생여부
            error (str): 에러

        """
        tr_id = os.getenv("INQ_PSBL_CANCEL_TR_ID")
        api = "uapi/domestic-stock/v1/trading/inquire-psbl-rvsecncl"

        data = {
            # 계좌번호
            "CANO": os.getenv("ACCOUNT_FRONT"),
            "ACNT_PRDT_CD": os.getenv("ACCOUNT_REAR"),
            # 한국거래소전송주문조직번호
            "INQR_DVSN_1": inqr_dvsn_1,
            "INQR_DVSN_2": inqr_dvsn_2,
        }

        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {self.access_token}",
            "appKey": self.app_key,
            "appSecret": self.app_secret,
            "tr_id": tr_id,
            # 개인
            "custtype": "P",
            "hashkey": self.hashkey(data),
        }

        return self._request(api, data, headers, method="GET")

    def get_reserved_orders(self, rsvn_ord_start_dt: str, rsvn_ord_end_dt: str):
        """
        국내 예약 주문 조회
        예약 주문 내역을 전체를 확인할 수 있다.

        Returns:
            status_code (str): 상태 코드, (200 | 4xx | 5xx)
            output (dict): 다음 주문 결과 dict를 list로 갖는다.
            error (str): 에러

        """
        tr_id = os.getenv("RSVN_ORD_TR_ID")
        api = "uapi/domestic-stock/v1/trading/order-resv-ccnl"

        data = {
            # 예약주문일자
            "RSVN_ORD_ORD_DT": rsvn_ord_start_dt,
            "RSVN_ORD_END_DT": rsvn_ord_end_dt,
            "RSVN_ORD_SEQ": "",
            # 단말매체종류카드
            "TMNL_MDIA_KIND_CD": "00",
            # 계좌번호
            "CANO": os.getenv("ACCOUNT_FRONT"),
            "ACNT_PRDT_CD": os.getenv("ACCOUNT_REAR"),
            "PRCS_DVSN_CD": "0",
            "CNCL_YN": "Y",
            # 종목코드 (공백 시 전체)
            "PDNO": "",
            "SLL_BUY_DVSN_CD": "",
            "CTX_AREA_FK200": "",
            "CTX_AREA_NK200": "",
        }

        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {self.access_token}",
            "appKey": self.app_key,
            "appSecret": self.app_secret,
            "tr_id": tr_id,
            # 개인
            "custtype": "P",
            "hashkey": self.hashkey(data),
        }

        return self._request(api, data, headers, method="GET")

    # inquire_balance는 API response지만 get_balance는 직접 남은 예수금을 가져온다.
    def get_balance(self):
        response_json = self.inquire_balance()
        # 참조: https://apiportal.koreainvestment.com/apiservice/apiservice-domestic-stock-order#L_66c61080-674f-4c91-a0cc-db5e64e9a5e6
        response_json["output"] = {
            "dnca_tot_amt": response_json["output"]["output2"][0]["dnca_tot_amt"],
            "prvs_rcdl_excc_amt": response_json["output"]["output2"][0]["prvs_rcdl_excc_amt"],
        }

        return response_json


if __name__ == "__main__":
    import argparse

    argparse = argparse.ArgumentParser()
    argparse.add_argument("--mode", type=str, default="PROD")
    args = argparse.parse_args()

    mode = args.mode

    if mode == "PROD":
        file_name = "prod.env"
    else:
        file_name = "dev.env"

    trader = Trader(
        app_key=os.getenv("APP_KEY"), app_secret=os.getenv("APP_SECRET"), url_base=os.getenv("BASE_URL"), mode=mode
    )
    #
    # res = trader.get_credential_access_token()

    # print(f"res : {res}")
    # trader.set_credential_access_token(token)

    res = trader.inquire_balance()
    #
    # res = trader.rsvn_stock(
    #     stock_code="453810",
    #     ord_qty=1,
    #     ord_price=13600
    # )
    print(res)
    print(res["output"]["output2"])
