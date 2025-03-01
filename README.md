# 📈Auto-Trade
**적립식 주식 매수 방식의 수익 극대화**

Auto Trade는 포트폴리오를 구성한 뒤, 이들 종목에 대해 매월 매수 혹은 매도하는 자동매매 프로그램입니다.

저는 주식 투자를 하고 싶었지만 매일 차트를 보며 매수/매도 시점을 잡느라 에너지를 쓰고 싶지 않았습니다.

또한 제게는 시장의 흐름을 읽을 정도의 경제적 지식도 없습니다.

적립식 장기투자이니 매수는 항상 발생합니다. 다만 언제 사느냐가 중요하겠지요.

이 프로젝트는 종가 예측 모델과 몇 가지 로직을 연계해 매매 타이밍을 결정합니다.

내 전략을 코드로 녹여내고 예측 모델을 엮어 자동매매를 실행시켜놓고 나는 신경 끄는 것.

그것이 이 프로젝트로 이루고자 하는 궁극적인 목표입니다.

(단, 저는 외부조건들을 최대한 고려하지 않아도 되고 경향성만 따르기 위해 ETF 종목들만을 담았습니다.)

## Composition
파일 구성은 크게 두 개의 디렉토리 구조로 구분되어 있습니다.

- FastAPI 서버 파트
	- 구매, 조회, 갱신 등의 실질적 행동을 수행하는 서버입니다.
	    - 한국투자증권 API를 활용한 주식 매매, 주문 조회 등의 API
	    - DB에 저장된 사용자의 자산 정보 API
	    - slackbot API
- airflow 파트
    - 자동매매에 필요한 논리적 행동들을 스케쥴링합니다.
	    - ex1) 매일 한투 API 토큰을 갱신한다.
	    - ex2) 매일 내 포트폴리오 종목들의 한달 뒤 종가를 예측한다.
	- 되도록 모든 action은 API를 호출해 수행합니다.

## Architecture
![](https://i.imgur.com/0eN6xkN.png)

## Installation
Open a terminal and run:
```
$ conda create -n auto-trade python=3.9
$ conda activate auto-trade

$ pip3 install -r requirements.txt
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
