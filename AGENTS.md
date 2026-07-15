# AGENTS.md — 개발 지침서

## 프로젝트 철학

**"무조건 돈을 벌어야 한다. 매매가 발생하지 않으면 수익도 없다."**

이 프로젝트는 **공격적 DCA(Dollar Cost Averaging)** 전략을 기반으로 한 자동매매 시스템입니다.
핵심 원칙:

1. **매수는 무조건 실행한다** — 시장이 열려있으면 매일 분할매수
2. **매도(리스크 관리)는 엄격하게 유지한다** — 손절/트레일링 스탑은 절대 완화하지 않음
3. **매수 차단 조건은 극단적 상황만** — 갭다운 8%+, 포트폴리오 드로다운 10%+ 만 차단

---

## 전략 구조

### 매수 (Aggressive DCA)

```
시장 오픈 → 즉시 전 종목 순회 → 무조건 분할매수 실행
```

**차단되는 경우 (극단적 상황만):**
- 갭다운 > 8% (패닉 매도 구간)
- 가용 현금 < 1주 가격
- 계좌 제한 (APBK1680/1681 에러)

**차단하지 않는 것 (절대 추가 금지):**
- ❌ MA20/MA5 하회
- ❌ AI 감성 분석
- ❌ 상관 그룹 한도
- ❌ Losing Streak (손절 누적)
- ❌ 연속 하락 (10% 미만)
- ❌ 거래량 부족

### 물타기 (Averaging Down)

```
보유 종목이 매수가 대비 -2% 이상 하락 → 동일 금액 추가 매수 (평단가 하락)
```

- 세션당 종목별 최대 2회
- 재평가 주기: 60분
- 손절선(-4%) 이하 하락 시 → 물타기 대신 손절매 실행

### 매도 (리스크 관리 — 변경 금지)

| 규칙 | 조건 | 동작 |
|------|------|------|
| Stop Loss | 손익 <= -4% | 즉시 전량 매도 |
| Trailing Stop | 고점 대비 -2.5% 하락 (활성: +4% 도달 후) | 전량 매도 |
| Breakeven Stop | +2.5% 도달 후 매수가+0.2%로 하락 | 전량 매도 |
| Trend-Collapse | MA20 하회 + 손실 구간 | 즉시 매도 |
| Partial TP | 트레일링 활성가 도달 | 50% 부분 익절 |
| ATR Dynamic | ATR 기반 동적 손절폭 | 변동성 적응 |

---

## 코드 수정 규칙

### 🚫 절대 하지 말 것

1. **매수 조건을 추가하지 마라** — `attempt_aggressive_dca_buy` 에 새 차단 조건 절대 추가 금지
2. **AI 분석을 매수 결정에 연동하지 마라** — 정보 제공만 허용, veto 금지
3. **손절 기준을 완화하지 마라** — -4%는 최소 기준
4. **매수 세션 제한을 추가하지 마라** — max_buys_per_session은 충분히 높게 유지

### ✅ 해야 할 것

1. **매수가 실행되는지 매일 확인** — 로그에 "공격적 DCA 매수 성공" 메시지가 있어야 함
2. **매도가 정확히 동작하는지 확인** — 손절/트레일링 스탑 로그 확인
3. **에러 발생 시 즉시 알림** — Telegram으로 전달되는지 확인
4. **코드 수정 후 반드시 `python3 -c "import ast; ast.parse(open('run_bot.py').read())"` 실행**

---

## 환경 설정

### .env 필수 값

```env
KIS_MOCK=False          # 실투자 필수
KIS_APP_KEY=...
KIS_APP_SECRET=...
KIS_CANO=...
KIS_ACNT_PRDT_CD=01
```

### user_config.json 핵심 설정

```json
{
  "strategy": "aggressive_dca",
  "auto_strategy": false,
  "aggressive_dca": {
    "averaging_down_enabled": true,
    "averaging_down_trigger_pct": -2.0,
    "averaging_down_max_per_session": 2,
    "panic_gap_down_threshold_pct": 8.0,
    "skip_ai_check": true,
    "skip_trend_filter": true,
    "instant_buy_on_open": true
  }
}
```

---

## 테스트 방법

```bash
# 1. 구문 검증
python3 -c "import ast; ast.parse(open('run_bot.py').read())"

# 2. 단위 테스트
pytest tests/ -v

# 3. 모의투자 테스트 (선택)
KIS_MOCK=True python3 run_bot.py

# 4. 실투자 실행
python3 run_bot.py
```

---

## Git 커밋 규칙

- 모든 수정 후 자동 커밋/푸시
- 커밋 메시지 형식: `feat:`, `fix:`, `refactor:`, `docs:`
- 매수 차단 조건 추가 시 반드시 별도 branch에서 작업 후 리뷰

---

## 아키텍처 개요

```
run_bot.py (메인 봇)
├── config.py (환경변수)
├── user_config.json (사용자 설정)
├── strategies/
│   ├── volatility_breakout.py (VBO 타겟 계산 — day/swing 전략용)
│   ├── technical.py (MA, 갭다운, 연속하락 계산)
│   └── adaptive_volatility.py (적응형 전략 — 미사용)
├── modules/
│   ├── kis_api.py (해외 주식 API)
│   ├── kis_domestic.py (국내 주식 API)
│   ├── kis_websocket.py (실시간 가격 스트리밍)
│   ├── multi_llm.py (AI 합의 — aggressive_dca에서 비활성)
│   ├── auto_strategy.py (자동 전략 전환 — aggressive_dca에서 비활성)
│   ├── portfolio_manager.py (동적 포트폴리오 생성)
│   ├── telegram_notifier.py (알림)
│   └── trade_journal.py (거래 기록)
├── database/ (JSON 기반 데이터)
└── web/ (FastAPI 대시보드)
```
