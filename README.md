# 📈Auto-Trade
**적립식 주식 매수 방식의 수익 극대화**

Auto Trade는 포트폴리오를 구성한 뒤, 이들 종목에 대해 매월 매수 혹은 매도하는 자동매매 프로그램입니다.

저는 주식 투자를 하고 싶었지만 매일 차트를 보며 매수/매도 시점을 잡느라 에너지를 쓰고 싶지 않았습니다.

또한 제게는 시장의 흐름을 읽을 경제적 지식도 없습니다.

적립식 장기투자이니 매수는 항상 발생합니다. 다만 언제 사느냐가 중요하겠지요.

이 프로젝트는 종가 예측 모델과 몇 가지 로직을 연계해 매매 타이밍을 결정합니다.

내 전략을 코드로 녹여내고 예측 모델을 엮어 자동매매를 실행시켜놓고 나는 신경 끄는 것.

그것이 이 프로젝트로 이루고자 하는 궁극적인 목표입니다.

(단, 저는 외부조건들을 최대한 고려하지 않고 경향성만 따르기 위해 ETF 종목들만을 담았습니다.)

## Composition
파일 구성은 크게 두 개의 디렉토리로 구성되어 있습니다.

- FastAPI 서버 파트
	- 구매, 조회, 갱신 등의 실질적 행동을 수행하는 서버입니다.
	    - 한국투자증권 API를 활용한 주식 매매, 주문 조회 등의 API
	    - DB에 저장된 사용자의 자산 정보 API
	    - slackbot API
	    - LLM 전략 모듈 (OpenRouter 무료 모델 기반)
- airflow 파트
    - 자동매매에 필요한 논리적 행동들을 스케쥴링합니다.
	    - ex1) 매일 한투 API 토큰을 갱신한다.
	    - ex2) 매일 내 포트폴리오 종목들의 한달 뒤 종가를 예측한다.
	    - ex3) LLM을 활용해 경제적 근거와 함께 매매 의사결정을 한다.
	- 되도록 모든 action은 API를 호출해 수행합니다.

## Architecturehttps://github.com/tofulim/auto_trade/issues
![](https://i.imgur.com/0eN6xkN.png)

## Installation
Open a terminal and run:
```
# 'docker compose up --build' will run
$ run.sh
```

## Insert your private keys & tokens
fix `.fastapi.env.example`  !
```
# 한투 실전투자계좌 정보(PROD)
APP_KEY={ENTER_YOUR_PRIVATE_INFO}
APP_SECRET={ENTER_YOUR_PRIVATE_INFO}

# 한투 계좌번호(계좌번호 앞자리)
ACCOUNT_FRONT={ENTER_YOUR_PRIVATE_INFO}
ACCOUNT_REAR={ENTER_YOUR_PRIVATE_INFO}

# 한투 API 접근 토큰(초기 NULL이고 갱신하여 사용)
KIS_ACCESS_TOKEN={ENTER_YOUR_PRIVATE_INFO}

# Slack 토큰
SLACK_BOT_TOKEN={ENTER_YOUR_PRIVATE_INFO}

# OpenRouter API 키 (LLM 전략용)
OPENROUTER_API_KEY={ENTER_YOUR_PRIVATE_INFO}
# 무료 모델 자동 선택. 특정 무료 모델의 ID(:free)로 변경 가능
OPENROUTER_MODEL=openrouter/free
```

then rename it!
```
$ mv .fastapi.env.example .fastapi.env
```

## 절반 익절과 런타임 설정

`take_profit_dag`는 한국시간 평일 **20시에 하루 한 번** 계좌의 모든 국내주식/ETF를 확인합니다.
잔고의 현재가 대신 KRX 일별 시세 API의 **당일 종가**를 사용합니다.
기본값은 **평균 매입단가 대비 종가 수익률이 50% 이상이면 보유 수량의 절반을 한 번 예약매도**입니다.
예약 종료일을 비운 일반 시장가 예약으로 접수하여 주말·휴장일을 건너뛴 다음 거래일에 매도합니다.
100에 매수한 종목이 150이 되면 적용되며, 11주를 보유했다면 5주를 매도합니다.
1주만 보유하면 매도하지 않습니다. 수수료와 세금은 목표 수익률 계산에 포함하지 않습니다.
장중에만 기준을 넘었다면 매도하지 않습니다. 실제 체결 가격은 다음 거래일 가격이므로 종가와 다를 수 있습니다.
FastAPI는 평일·비공휴일의 15:40~23:40에만 접수하고, 당일 종가가 없으면 새 주문을 만들지 않습니다.
현재 증권사 연동이 국내주식 API이므로 해외주식에는 적용되지 않습니다.

설정 조회:

```sh
curl http://localhost:8000/v1/settings/trading
```

설정 변경 (생략한 필드는 유지):

```sh
curl -X PUT http://localhost:8000/v1/settings/trading \
  -H 'Content-Type: application/json' \
  -d '{"take_profit_threshold": 50.0}'
```

| 필드 | 초기 기본값 | 의미 |
| --- | --- | --- |
| `take_profit_threshold` | `50.0` | 익절 기준 수익률(%), 양수 |
| `purchase_threshold` | `3.0` | 기존 예측 전략의 매수 기준 변화율(%) |
| `sell_threshold` | `-25.0` | 기존 예측 전략의 매도 기준 변화율(%) |
| `period_days` | `30` | Prophet 예측 및 LLM 분석 기간, 1~365일 |

설정과 익절 기록은 기존 `DATABASE_PATH`의 SQLite에 저장됩니다. 컨테이너 재생성 시에도
기존 `/database` 볼륨을 유지하면 보존됩니다. 이 기능을 처음 배포할 때는 FastAPI와 Airflow 이미지를
한 번 갱신해야 하지만, 이후 숫자 변경은 빌드나 재시작 없이 다음 실행부터 반영됩니다.
`/database` 볼륨에는 예전 `database.py`도 남아 있을 수 있으므로, 테이블 모델은 볼륨 외부의
`entity` 패키지에서 등록합니다. 서버 시작 시 기존 자산·포트폴리오 데이터는 유지하면서 누락된 테이블만 생성합니다.
환경변수는 FastAPI 설정 테이블을 **최초 생성할 때만** 초기값으로 사용합니다.
기존 Airflow의 `PURCHASE_THRESHOLD`, `SELL_THRESHOLD`는 더 이상 읽지 않으므로,
운영값이 위 기본값과 다르면 배포 시 API로 설정하거나 최초 FastAPI 환경변수에 옮기세요.
월 투자금·자동이체일과 인증정보·호스트 등 나머지 환경변수는 기존 방식대로 유지합니다.

익절 상태 조회와 수동 검사 (장 마감 후에는 실제 예약매도를 접수할 수 있음):

```sh
curl http://localhost:8000/v1/trader/take_profit
curl -X POST http://localhost:8000/v1/trader/take_profit/check
```

예약주문순번으로 접수(`accepted`)와 체결 완료(`completed`)를 구분합니다.
같은 날 재실행해도 예약을 중복 접수하지 않습니다. 일반예약 처리일의 장 마감 후 또는 취소 확인 후에는
이미 체결된 수량을 제외한 원래 익절 목표의 잔량만 당일 종가 조건 충족 시 다음 거래일 예약으로 재시도합니다.
매도 가능 수량이 목표 잔량보다 부족하면 기다립니다. 추가 매수·수익률 재상승·설정 변경으로
익절 완료 상태가 초기화되지는 않습니다. 전량 청산을 검사에서 확인한 뒤 재매수하면 다시 적용됩니다.
검사 사이에 청산과 재매수가 모두 이루어지면 새 보유 구간으로 인식하지 못합니다.
기존 예측 전략의 매수·매도 로직은 별도로 계속 실행됩니다. 익절 예약매도는 월 매수 예산을 변경하지 않습니다.

접수 중단(`pending`)이나 결과 불명(`unknown`)은 재시작 후에도 자동 재접수를 차단합니다.
이 상태는 증권사 주문 내역과 DB 기록을 대조하여 실제 접수 여부를 확인한 뒤 운영자가 복구해야 합니다.
체결 조회 실패나 주문 내역 불일치도 신규 주문으로 해결하지 않고 검사 실패로 표시합니다.
설정 API는 기존 다른 API와 동일한 접근 제어를 따릅니다.

한투 잔고·체결 조회는 [한국투자증권 공식 API 예제](https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock)를 기준으로 연속 조회를 처리합니다.

## Run
Open a terminal and run:

### just deploy and try
```
# FastAPI 서버 실행
$ python3 fastapi_server/main.py

$ cd airflow

# Airflow 스케쥴러 실행
$ airflow scheduler

# Airflow 웹서버 실행 (ui 가진 컨트롤 페이지)
$ airflow webserver --port 8080
```

fastapi 서버와 각 airflow scheduler와 webserver는 각각의 tmux 세션에서 수행하였습니다.


### prerequisite
- 환경
    - 본 프로젝트는 EC2 free tier 장비에서 수행되었습니다.
	    - t2.micro (1 vCPU / 1GB RAM / 25 GB storage)
	- swap memory를 사용하지 않으면 airflow를 작동시키는 데 어려움이 있을 수 있습니다.


    ```
    # check swap memory
    $ free

    # create swap file
    $ sudo fallocate -l 2g /swapfile

	# change permission
	$ sudo chmod 600 /swapfile

	# apply swapfile
	$ sudo mkswap /swapfile
	$ sudo swapon /swapfile

	# activate swapfile when boot
	$ sudo vi /etc/fstab

	# 마지막줄에 다음 내용 추가
	/swapfile swap swap defaults 0 0

	# check swap file
	$ free -h
    ```

- 한국투자증권 API 관련
	- 본 프로젝트는 한투 API를 사용하고 있습니다.
		- https://apiportal.koreainvestment.com/intro
	- API 를 신청하고 계좌를 개설한 뒤 사용할 수 있습니다.

## Limitation of this project
본 프로젝트는 몇 가지 가정을 전제로 하고 있습니다.
- 장기투자
	- 매도는 적고 절대적으로 매수가 많음
- ETF 타겟
	- 종합적 묶음 종목으로 개별 외부 요인 영향을 최대한 덜받기 위함
	- 종가 예측 모델을 활용해 경향을 판단할 수 있는 종목
- 예약매수 사용
	- 기본적인 동작은 하루 시장이 끝난 뒤 종가를 예측하여 다음 날 장시작 때 매매하도록 예약 매매하는 것 입니다.
	- 매매 동작에 대한 알림은 slack을 통해 전해지고 메시지를 받은 후로부터 최소 12시간 뒤에 실제 매매가 이루어지므로 나도 모르게 매매가 이루어지는 것은 방지할 수 있습니다.

## Feature Examples
### LLM 활용 매매 전략 (새로운 기능)
#### AI 기반 의사결정
- OpenRouter 무료 모델을 활용해 경제적 근거와 함께 매매 결정을 제공한다.
- 기존 Prophet 모델 및 통계 분석과 함께 종합적인 판단을 수행한다.
- 높은 신뢰도(>0.7)의 AI 분석이 기존 지표와 일치할 때 우선적으로 반영된다.
<img width="673" height="419" alt="image" src="https://github.com/user-attachments/assets/f1674907-6e9f-4789-bfab-53f2d74d0b6a" />


#### 경제적 근거 제공
- 각 매매 결정에 대한 상세한 경제적 분석과 근거를 제공한다.
- 사용자가 AI의 판단을 검토하고 학습할 수 있도록 돕는다.
- 예약 매수 특성상 다음 날 오전 실행 전 취소 가능하다.

### daily_report
#### 종가 예측
- 한 달 뒤 종가를 예측하고 오늘 대비 몇 퍼센트 등락할 지 그래프와 함께 반환한다.
- ![](https://i.imgur.com/eektW3g.png)

#### 예측에 대한 행동 결정
- 예측한 변화율 혹은 여러 통계적 지표에 따라 매수/매도 행동을 결정한다.
- ![](https://i.imgur.com/kYAxuai.png)

### monthly_report
- 월간 리포트로 내가 구매한 가격이 최저 종가 대비 얼마나 비싸게 샀는지 알 수 있다.
- 이를 통해 내 포트폴리오 전략에 대해 점검할 수 있다.
![](https://i.imgur.com/3yKoqaC.png)
