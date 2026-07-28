# AGENTS.md — 개발 지침서

## 프로젝트 철학 (v5.0 — 전면 개편)

**"첫째, 잃지 않는다. 둘째, 첫째 원칙을 잊지 않는다. 그 다음에 번다."**

> v4.0(2026-06-24)은 "무조건 돈을 벌어야 한다 → 매수는 무조건 실행한다"를 원칙으로 삼고
> AI 뉴스 체크와 추세 필터를 전부 꺼버렸다(`skip_ai_check=True`, `skip_trend_filter=True`).
> 그 결과 2026-07 중국발 반도체 수출 규제 뉴스로 반도체 업종 전체가 붕괴하는 와중에도
> 봇은 이 사실을 전혀 인지하지 못한 채 SOXL/SMH를 매일 기계적으로 물타기 매수했고,
> 몇 주간 큰 손실을 냈다. **"매수가 발생해야 수익이 난다"는 명제 자체는 맞지만,
> "그러니 조건 없이 사라"는 결론은 틀렸다.** v5.0은 이 인과관계를 바로잡는다.

핵심 원칙:

1. **매수는 게이트를 통과해야만 실행한다** — 추세/뉴스/섹터/상관/손실누적 게이트 중
   하나라도 걸리면 사지 않는다. "공격적"이라는 이름은 매수 "조건 없음"이 아니라
   매수 "주기(자주 분할매수)"를 뜻한다.
2. **뉴스를 무시하지 않는다** — 시장 전체 뉴스뿐 아니라, 종목이 속한 **섹터 단위**
   뉴스(예: 반도체 수출 규제)를 별도로 확인해 "시장은 멀쩡한데 이 섹터만 무너지는"
   상황을 놓치지 않는다 (`modules/sector_news.py`).
3. **매도(리스크 관리)는 엄격하게 유지한다** — 손절/트레일링 스탑은 절대 완화하지 않음.
4. **서킷브레이커는 실제로 매매를 멈춰야 한다** — 알림만 보내고 매수는 계속되는 것은
   서킷브레이커가 아니다 (v4.0의 포트폴리오 드로다운 체크가 이 함정에 빠져 있었음).
5. **한국장과 미국장은 다른 시장이다** — 같은 코드 경로를 쓰더라도, AI 판단 성향
   (persona)과 추세 확인 강도는 시장별로 다르게 적용한다 (아래 "시장별 차별화" 참조).

---

## 시장별 차별화 (v5.0 신규)

| 항목 | 🇺🇸 US | 🇰🇷 KR |
|------|--------|--------|
| AI 페르소나 | `neutral` (균형) | `conservative` (보수적 — 국내 개별 이슈 변동성이 커서 더 엄격) |
| 추세 확인 | 20MA(1x) / 10MA(레버리지) 상회 | 20MA **AND** 5MA 동시 상회 (더 엄격) |
| 개별 종목 | ETF만 (개별주 편입 중단, 2026-07-07 v3.1) | ETF만 (개별주 편입 중단, 동일) |
| 레버리지 | 3배 ETF 제한 없음 (TQQQ/SOXL/TECL 등) | 예탁금 1,000만원 이상만 2배 ETF 허용 |
| 뉴스 언어 | 영문 (Google News RSS, `hl=en-US`) | 국문 (Google News RSS, `hl=ko`) |

시장별 설정은 `user_config.json`의 `market_settings.us` / `market_settings.kr`로 override 한다
(`get_effective_market_config()`가 병합).

---

## 전략 구조

### 매수 (Guarded Aggressive DCA — 내부 코드명은 `aggressive_dca` 유지)

```
시장 오픈 → 전 종목 순회 → 게이트 통과 시에만 분할매수 실행
```

**게이트 순서 (`run_bot.py` STRATEGY_MODE == 'aggressive_dca' 블록):**

1. 패닉 갭다운 > 8% → 하루 대기
2. 가용 현금 부족
3. 포트폴리오 드로다운 서킷브레이커 (`portfolio_drawdown_pct`, 기본 7%) — **실제로 매수를 막음**
4. 추세 이탈 (US: 20MA/10MA, KR: 20MA+5MA)
5. 상관 그룹 한도 초과 (`correlation_max_per_group`, 기본 2)
6. 일일 손실 누적 서킷브레이커 (`losing_streak_*`)
7. AI 시장 전반 뉴스 veto (`ai.check_market_sentiment`)
8. **[신규] AI 섹터 특화 뉴스 veto** (`modules/sector_news.py` + `ai.check_sector_sentiment`) —
   종목이 속한 섹터(반도체/나스닥테크/2차전지 등)에 국한된 크래시만 판별하여, 관련 없는
   다른 섹터의 매수 기회까지 막지 않는다. 페르소나와 무관하게 항상 엄격하게 판단한다
   (aggressive 페르소나로도 이 게이트는 완화되지 않음 — `GeminiAnalyst.check_sector_crash`).

각 설정은 `user_config.json`의 `aggressive_dca` 블록에서 개별적으로 끌 수 있으나
(`skip_ai_check`, `skip_trend_filter`, `skip_correlation_check`, `sector_news_veto_enabled`),
**기본값은 전부 게이트 ON(False/True 적절히)이다.** 이 기본값을 다시 끄는 것은
v4.0으로 회귀하는 것이므로, 끌 때는 반드시 별도 branch + 리뷰를 거친다.

### 물타기 (Averaging Down)

```
보유 종목이 매수가 대비 -3% 이상 하락 → 섹터 뉴스가 정상이면 동일 금액 추가 매수
```

- 세션당 종목별 최대 2회, 재평가 주기 60분
- 손절선(-4%) 이하 하락 시 → 물타기 대신 손절매 실행
- 포트폴리오 드로다운 서킷브레이커 활성 시 → 물타기도 중단
- **[신규] 섹터 뉴스가 CRASH/HIGH면 물타기 금지** — 무너지는 섹터에 계속 자금을 붓지 않음

### 매도 (리스크 관리 — 변경 금지)

| 규칙 | 조건 | 동작 |
|------|------|------|
| Stop Loss | 손익 <= -4% | 즉시 전량 매도 |
| Trailing Stop | 고점 대비 -2.5% 하락 (활성: +4% 도달 후) | 전량 매도 |
| Breakeven Stop | +2.5%~+3% 도달 후 매수가+0.2%로 하락 | 전량 매도 |
| Trend-Collapse | MA20 하회 + 손실 구간 | 즉시 매도 |
| Partial TP | 트레일링 활성가 도달 | 50% 부분 익절 |
| ATR Dynamic | ATR 기반 동적 손절폭 | 변동성 적응 |
| Portfolio Drawdown | 전체 손실 -7% 이상 | 신규 매수 전면 중단 (매도 아님, 서킷브레이커) |

---

## 코드 수정 규칙

### 🚫 절대 하지 말 것

1. **매수 게이트를 몰래 끄지 마라** — `skip_ai_check`/`skip_trend_filter`/
   `skip_correlation_check`/`sector_news_veto_enabled`의 기본값을 다시 완화하려면
   반드시 별도 branch + 리뷰. v4.0 사고의 재발 지점이 정확히 여기였다.
2. **AI 분석 결과를 무시하지 마라** — 섹터 veto는 자본보호 전용 게이트이며,
   aggressive 페르소나라도 완화되어서는 안 된다.
3. **손절 기준을 완화하지 마라** — -4%는 최소 기준.
4. **서킷브레이커를 "알림만 보내는 로직"으로 되돌리지 마라** — 반드시 실제 매수 차단
   플래그(`portfolio_drawdown_halt` 등)로 이어져야 한다.

### ✅ 해야 할 것

1. **매수가 실행되는지, 그리고 "왜 실행되지 않았는지"도 매일 확인** — 로그에
   "공격적 DCA 매수 성공" 또는 매수 차단 사유(`skipped_buy_reasons`)가 있어야 함.
2. **세션 매수 0건 워치독 알림을 무시하지 마라** — `session_buy_count == 0`으로
   세션이 끝나면 Telegram 경고가 온다. 원인(API 실패/전량 게이트 차단)을 반드시 확인.
3. **매도가 정확히 동작하는지 확인** — 손절/트레일링 스탑 로그 확인.
4. **에러 발생 시 즉시 알림** — Telegram으로 전달되는지 확인. `except: pass` 로
   조용히 삼키는 패턴을 새로 추가하지 말 것 (과거 US 세션이 몇 주간 조용히 죽어있던
   사고가 반복적으로 이 패턴에서 발생했음 — 2026-05-26, 2026-06-24, 2026-07 추정).
5. **코드 수정 후 반드시** `python -c "import ast; ast.parse(open('run_bot.py').read())"` 실행.

---

## 환경 설정

### .env 필수 값

```env
KIS_MOCK=False          # 실투자 필수
KIS_APP_KEY=...
KIS_APP_SECRET=...
KIS_CANO=...
KIS_ACNT_PRDT_CD=01
GEMINI_API_KEY=...       # 섹터 뉴스 veto가 Gemini에 의존하므로 사실상 필수
```

### user_config.json 핵심 설정 (v5.0)

```json
{
  "strategy": "aggressive_dca",
  "persona": "neutral",
  "market_settings": {
    "us": { "persona": "neutral" },
    "kr": { "persona": "conservative" }
  },
  "llm_consensus": {
    "crash_veto": true,
    "required_buy_ratio": 0.5
  },
  "aggressive_dca": {
    "averaging_down_enabled": true,
    "averaging_down_trigger_pct": -3.0,
    "averaging_down_max_per_session": 2,
    "panic_gap_down_threshold_pct": 8.0,
    "portfolio_drawdown_halt_pct": 7.0,
    "skip_ai_check": false,
    "skip_trend_filter": false,
    "skip_correlation_check": false,
    "sector_news_veto_enabled": true
  },
  "risk_management": {
    "correlation_cap_enabled": true,
    "losing_streak_enabled": true,
    "portfolio_drawdown_pct": 7.0
  }
}
```

---

## 테스트 방법

```bash
# 1. 구문 검증
python -c "import ast; ast.parse(open('run_bot.py').read())"

# 2. 단위 테스트 (v5.0 신규 테스트 포함)
pytest tests/ -v
pytest tests/test_v50_strategy.py -v   # 섹터 veto / 게이트 기본값 전용

# 3. 모의투자 테스트 (선택)
KIS_MOCK=True python3 run_bot.py

# 4. 실투자 실행
python3 run_bot.py
```

---

## Git 커밋 규칙

- 모든 수정 후 자동 커밋/푸시
- 커밋 메시지 형식: `feat:`, `fix:`, `refactor:`, `docs:`
- 매수 게이트를 약화(끄기/완화)하는 변경은 반드시 별도 branch에서 작업 후 리뷰

---

## 아키텍처 개요

```
run_bot.py (메인 봇)
├── config.py (환경변수)
├── user_config.json (사용자 설정 — market_settings로 KR/US 차별화)
├── strategies/
│   ├── volatility_breakout.py (VBO 타겟 계산 — day/swing 전략용)
│   ├── technical.py (MA, 갭다운, 연속하락 계산)
│   └── adaptive_volatility.py (적응형 전략 — 미사용)
├── modules/
│   ├── kis_api.py (해외 주식 API)
│   ├── kis_domestic.py (국내 주식 API)
│   ├── kis_websocket.py (실시간 가격 스트리밍)
│   ├── multi_llm.py (AI 합의 — 시장 전반 + 섹터 특화 veto)
│   ├── sector_news.py ([v5.0 신규] 종목→섹터 매핑, 섹터 뉴스 쿼리)
│   ├── gemini_analyst.py (뉴스 수집 + 섹터 크래시 판별 — persona 무관 엄격 모드)
│   ├── auto_strategy.py (자동 전략 전환)
│   ├── portfolio_manager.py (동적 포트폴리오 생성 — 추세추종 복합 점수)
│   ├── telegram_notifier.py (알림)
│   └── trade_journal.py (거래 기록)
├── database/ (JSON 기반 데이터)
├── docs/
│   └── baseknowledge.md ([v5.0 신규] 퀀트투자 입문자용 용어/개념 설명)
└── web/ (FastAPI 대시보드)
```

## 루프 엔지니어링 (전략 검증)

v5.0부터 "전략이 설계대로 동작하는지"를 세 계층으로 확인한다.

1. **세션 내 자가 점검 (코드)** — `session_buy_count`가 0인 채로 세션이 끝나면
   후보 종목/차단 사유를 담아 Telegram 경고. 잔고 조회 실패(`get_foreign_balance`
   응답 이상) 시에도 즉시 경고.
2. **주간 백테스트 + OPRO 자동 최적화** — 기존 유지 (`modules/backtest_runner.py`,
   `modules/opro_optimizer.py`, 매주 일요일 07:00 KST).
3. **정기 원격 점검 (Claude 스케줄)** — 대시보드/로그를 주기적으로 점검해 매매가
   설계대로(게이트 통과 시에만) 이루어지고 있는지 사람이 읽을 수 있는 보고로 정리.
   설정: 저장소 루트의 스케줄 설정 참고, 또는 `/loop` 로 수동 재설정.
