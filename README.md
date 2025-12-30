# US-ETF-Sniper 🎯

미국 주식 레버리지 ETF 자동매매 봇 (AI + 변동성 돌파 전략)

## 📊 프로젝트 개요

나스닥/반도체 상승장에서 **3배 레버리지(3x)**로 수익을 극대화하되, AI로 하락장을 감지하여 **MDD(최대 낙폭)를 방어**하는 자동매매 시스템입니다.

### 핵심 대상 종목
- **TQQQ** (ProShares UltraPro QQQ) - 나스닥 100 지수 3배 추종
- **SOXL** (Direxion Daily Semiconductor Bull 3X) - 반도체 지수 3배 추종

## 🎯 투자 전략

1. **Trend Filter**: 20일 이동평균선 기반 추세 판단
2. **Entry Trigger**: 변동성 돌파(VBO) 전략으로 진입 타점 포착
3. **AI Macro Filter**: Google Gemini로 거시경제 뉴스 분석 및 리스크 필터링
4. **Exit Rule**: 3% 손절 / 트레일링 스탑 / 장 마감 전 전량 청산

## 🛠️ 기술 스택

- **Broker**: 한국투자증권 해외주식 API
- **AI Engine**: Google Gemini 1.5 Flash
- **Language**: Python 3.10+
- **Libraries**: pandas, requests, google-generativeai, schedule

## 📋 사전 준비

### 1. 한국투자증권 API Key 발급
1. [한국투자증권](https://www.koreainvestment.com/) 계좌 개설
2. 해외주식 거래 신청
3. Open API 신청 (모의투자 체크)
4. APP Key와 APP Secret 발급

### 2. Google Gemini API Key 발급
1. [Google AI Studio](https://aistudio.google.com/) 접속
2. API Key 발급 (무료 티어 사용 가능)

### 3. 환경 설정
`.env` 파일을 열어 다음 정보를 입력하세요:

```env
# 한국투자증권 API
KIS_APP_KEY=YOUR_APP_KEY
KIS_APP_SECRET=YOUR_APP_SECRET
KIS_CANO=YOUR_ACCOUNT_NO_PREFIX  # 계좌번호 앞 8자리
KIS_ACNT_PRDT_CD=YOUR_ACCOUNT_NO_SUFFIX  # 계좌번호 뒤 2자리
KIS_MOCK=True  # 실전투자 시 False로 변경

# Google Gemini API
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
```

## 🚀 실행 방법

### 설치
```bash
pip install -r requirements.txt
```

### 실행
```bash
# 스케줄러 모드 (매일 23:30 KST 자동 실행)
python run_bot.py

# 테스트 모드 (즉시 실행)
python run_bot.py --test
```

## 📁 프로젝트 구조

```
US-ETF-Sniper/
├── run_bot.py              # 메인 실행 파일
├── config.py               # 환경변수 설정
├── requirements.txt        # 필요 라이브러리
├── .env                    # API Key 관리 (보안 주의)
├── strategies/
│   ├── volatility_breakout.py  # 변동성 돌파 전략
│   └── technical.py        # 기술적 지표 계산
├── modules/
│   ├── kis_api.py          # 한국투자증권 API 래퍼
│   ├── gemini_analyst.py   # AI 뉴스 분석기
│   └── logger.py           # 로깅 시스템
└── database/               # 거래 로그 저장
```

## ⚠️ 주의사항

1. **리스크 관리**: 레버리지 ETF는 변동성이 크므로 소액으로 시작하세요.
2. **모의투자 필수**: 실전 투자 전 충분한 모의투자로 검증하세요.
3. **API 제한**: KIS API는 일일 호출 제한이 있으니 주의하세요.
4. **시세 신청**: 해외주식 실시간 시세를 미리 신청해야 합니다.

## 📝 라이센스

이 프로젝트는 교육 목적으로 제작되었습니다. 투자 손실에 대한 책임은 사용자에게 있습니다.
