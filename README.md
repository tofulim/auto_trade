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

## 주문 상태

DB와 API의 `order_status`에는 다음 단어를 저장하고, Slack 알림에는 한국어 상태명을 표시합니다.

| 저장 값 | 기존 코드 | 표시 이름 | 의미 |
| --- | --- | --- | --- |
| `NOT_ORDERED` | `N` | 주문 없음 | 초기 상태 또는 월 예산 배분 후 주문 전 상태 |
| `RESERVATION_ACCEPTED` | `O` | 예약 주문 접수 완료 | 예약 주문이 접수되어 결과 확인 대상인 상태 |
| `UNPROCESSED` | `F` | 미처리 | 증권사 조회 결과가 `미처리`인 상태. 현재 로직에서 다시 매수 판단 가능 |
| `PROCESSED` | `S` | 주문 처리 완료 | 증권사 조회 결과가 `처리`여서 매수 여부와 예산을 반영한 상태 |
| `RESULT_PENDING` | `W` | 처리 결과 확인 대기 | 조회 결과가 `처리`/`미처리` 외의 값이어서 다음 확인 대상인 상태 |
| `PROCESSING_ERROR` | `E` | 주문 결과 처리 중 오류 | 주문 결과를 읽거나 반영하는 과정에서 예외 발생 |

`PROCESSING_ERROR`는 주문 실패를 뜻하지 않습니다. 현재 예외 처리에서는 알림만 보내며 DB 상태는 덮어쓰지 않습니다.
예: `종목 TEST: 주문 결과 처리 중 오류 (주문 실패 여부는 별도 확인이 필요합니다.)`

FastAPI 서버가 시작되면 기존 알파벳 값을 위 저장 값으로 변환합니다. 이미 변환된 값과 예산·갱신 시각 등 다른 필드는 유지합니다.
기존 알파벳을 보내는 API 생성·수정 요청도 새 값으로 저장하며, Airflow는 전환 중 구형·신형 값을 모두 읽을 수 있습니다.
배포할 때는 구형 Airflow가 새 상태를 읽지 않도록 스케줄러를 중지한 뒤 FastAPI와 Airflow를 함께 갱신하고 다시 시작해야 합니다.
롤백 시에는 단어 상태도 읽을 수 있는 버전을 사용하거나 기존 코드로 데이터를 되돌려야 합니다.

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
