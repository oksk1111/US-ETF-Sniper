"""
다중 LLM 합의 시스템 (Multi-LLM Consensus Engine)

여러 무료 LLM의 의견을 수렴하여 다수결로 투자 판단을 내립니다.
- Gemini (Google): 뉴스 해석, 영어 역량
- Grok (xAI): X(트위터) 기반 실시간 분석
- DeepSeek: 아시아 시장 관점
- Groq (Llama): 초고속 추론, 보조 의견

합의 방식:
1. 각 LLM이 독립적으로 risk_level + can_buy 판단
2. 다수결 투표 (Majority Vote)
3. CRASH 판정이 하나라도 있으면 매수 차단
"""

import concurrent.futures
from modules.gemini_analyst import GeminiAnalyst
from modules.grok_analyst import GrokAnalyst
from modules.deepseek_analyst import DeepSeekAnalyst
from modules.groq_analyst import GroqAnalyst
from modules.logger import logger

# === [v2.5 refactor] Consensus 결과 캐시 ===
# 동일 뉴스 입력에 대해 짧은 시간 내 반복 질의 시 LLM API 호출/쿼터를 절약.
import hashlib
import time as _time

_CONSENSUS_CACHE: dict = {}
_CONSENSUS_CACHE_TTL_SEC = 300  # 5분

# [v5.0] 섹터 특화 뉴스 veto 캐시 — 종목마다 매 사이클 LLM을 호출하면 API 쿼터가
# 빠르게 소진되므로, 섹터 단위(반도체/나스닥 등)로 30분 캐시한다.
_SECTOR_CACHE: dict = {}
_SECTOR_CACHE_TTL_SEC = 1800  # 30분


def _cache_key(news_text: str, persona: str) -> str:
    h = hashlib.sha256(f"{persona}::{news_text or ''}".encode("utf-8")).hexdigest()
    return h[:32]


def _cache_get(key: str, store: dict = None, ttl: int = None):
    store = _CONSENSUS_CACHE if store is None else store
    ttl = _CONSENSUS_CACHE_TTL_SEC if ttl is None else ttl
    item = store.get(key)
    if not item:
        return None
    ts, value = item
    if _time.time() - ts > ttl:
        try:
            del store[key]
        except KeyError:
            pass
        return None
    return value


def _cache_put(key: str, value: dict, store: dict = None) -> None:
    store = _CONSENSUS_CACHE if store is None else store
    # 단순 LRU 흉내: 200개 초과 시 가장 오래된 항목 1개 제거
    if len(store) > 200:
        try:
            oldest = min(store.items(), key=lambda kv: kv[1][0])[0]
            del store[oldest]
        except Exception:
            pass
    store[key] = (_time.time(), value)


class MultiLLMAnalyst:
    def __init__(self, consensus_config=None):
        self.analysts = []
        self.analyst_names = []
        cfg = consensus_config or {}
        self.policy = {
            "crash_veto": cfg.get("crash_veto", True),
            "min_successful_llms": max(1, int(cfg.get("min_successful_llms", 1))),
            "required_buy_ratio": float(cfg.get("required_buy_ratio", 0.5)),
            "unknown_fallback_hold": cfg.get("unknown_fallback_hold", True),
            "tie_breaker": str(cfg.get("tie_breaker", "persona")).lower(),
        }
        
        logger.info("[MultiLLM] LLM 초기화 및 헬스체크 시작...")
        
        # 후보 LLM 목록 (이름, 인스턴스, 필수 여부)
        candidates = []
        
        # Gemini (기본)
        gemini = GeminiAnalyst()
        candidates.append(("Gemini", gemini))
        
        # Grok (선택)
        grok = GrokAnalyst()
        if grok.available:
            candidates.append(("Grok", grok))
        
        # DeepSeek (선택)
        deepseek = DeepSeekAnalyst()
        if deepseek.available:
            candidates.append(("DeepSeek", deepseek))
        
        # Groq (선택)
        groq = GroqAnalyst()
        if groq.available:
            candidates.append(("Groq", groq))
        
        # 헬스체크: 실제 API 호출로 사용 가능 여부 확인
        failed_llms = []
        for name, analyst in candidates:
            if hasattr(analyst, 'health_check'):
                passed = analyst.health_check()
                if passed and analyst.available:
                    self.analysts.append(analyst)
                    self.analyst_names.append(name)
                else:
                    failed_llms.append(name)
                    logger.warning(f"[MultiLLM] {name} 헬스체크 실패 → 합의 투표에서 제외")
            else:
                # health_check 미구현 시 available 플래그만 확인
                if analyst.available:
                    self.analysts.append(analyst)
                    self.analyst_names.append(name)
        
        if failed_llms:
            logger.warning(f"[MultiLLM] 제외된 LLM: {failed_llms}")
        
        if not self.analysts:
            logger.error("[MultiLLM] ⚠️ 활성 LLM이 없습니다! Gemini를 기본으로 추가합니다.")
            self.analysts.append(gemini)
            self.analyst_names.append("Gemini(fallback)")
        
        logger.info(f"[MultiLLM] 활성 LLM: {self.analyst_names} ({len(self.analysts)}개)")
        logger.info(
            "[MultiLLM] 합의정책: crash_veto=%s, min_successful_llms=%s, required_buy_ratio=%.2f, tie_breaker=%s",
            self.policy["crash_veto"],
            self.policy["min_successful_llms"],
            self.policy["required_buy_ratio"],
            self.policy["tie_breaker"],
        )

    def fetch_news(self):
        """뉴스 수집 (Gemini의 fetch_news 사용)"""
        # Gemini가 뉴스 수집 전담
        gemini = self.analysts[0]  # Gemini는 항상 첫 번째
        if hasattr(gemini, 'fetch_news'):
            return gemini.fetch_news()
        return ""

    def _query_single_llm(self, analyst, news_text, persona):
        """단일 LLM에 질의"""
        try:
            result = analyst.check_market_sentiment(news_text, persona=persona)
            return result
        except Exception as e:
            name = getattr(analyst, '__class__', type(analyst)).__name__
            logger.error(f"[MultiLLM] {name} query failed: {e}")
            return None

    def check_market_sentiment(self, news_text, persona="aggressive"):
        """
        다중 LLM 합의 기반 시장 감성 분석
        
        합의 규칙:
        1. 사용 가능한 LLM들에게 병렬로 질의
        2. CRASH 판정이 하나라도 있으면 매수 차단
        3. 나머지는 다수결 투표 (can_buy 기준)
        4. LLM 1개만 활성이면 해당 LLM의 판단을 따름
        """
        if not news_text:
            return {
                "risk_level": "LOW", 
                "can_buy": True,
                "market_condition": "NEUTRAL",
                "reason": "No news available, skipping AI check.",
                "consensus": "N/A",
                "votes": {}
            }
        
        # [v2.5] 캐시 히트 시 즉시 반환 (동일 뉴스 텍스트 5분 내 재질의 회피)
        _ck = _cache_key(news_text, persona)
        cached = _cache_get(_ck)
        if cached is not None:
            try:
                logger.info("[MultiLLM] consensus cache HIT — skipping LLM round-trip")
            except Exception:
                pass
            return cached
        
        # 병렬로 모든 LLM 질의
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(self._query_single_llm, analyst, news_text, persona): name
                for analyst, name in zip(self.analysts, self.analyst_names)
            }
            
            for future in concurrent.futures.as_completed(futures, timeout=30):
                name = futures[future]
                try:
                    result = future.result()
                    if result is not None:
                        # API 에러(UNKNOWN)는 투표에서 제외 - 실패한 LLM이 반대표로 집계되는 것 방지
                        if result.get('risk_level') == 'UNKNOWN':
                            logger.warning(f"[MultiLLM] {name}: API 에러로 투표 제외 - {result.get('reason', 'N/A')[:80]}")
                            continue
                        result["_name"] = name
                        results.append(result)
                        logger.info(f"[MultiLLM] {name}: risk={result.get('risk_level')}, buy={result.get('can_buy')}, reason={result.get('reason', 'N/A')[:50]}")
                except Exception as e:
                    logger.error(f"[MultiLLM] {name} 결과 처리 실패: {e}")
        
        if not results:
            logger.warning("[MultiLLM] 모든 LLM 응답 실패! 안전을 위해 매수 차단.")
            fallback_buy = not self.policy["unknown_fallback_hold"]
            return {
                "risk_level": "UNKNOWN",
                "can_buy": fallback_buy,
                "market_condition": "UNKNOWN",
                "reason": "All LLMs failed to respond.",
                "consensus": "ALL_FAILED",
                "votes": {}
            }

        if len(results) < self.policy["min_successful_llms"]:
            logger.warning(
                "[MultiLLM] 응답 LLM 수 부족(%s/%s)으로 매수 차단",
                len(results),
                self.policy["min_successful_llms"],
            )
            return {
                "risk_level": "HIGH",
                "can_buy": False,
                "market_condition": "NEUTRAL",
                "reason": f"Insufficient LLM quorum ({len(results)}/{self.policy['min_successful_llms']}).",
                "consensus": "QUORUM_BLOCK",
                "votes": {},
            }
        
        # 합의 처리
        votes = {}
        buy_votes = 0
        no_buy_votes = 0
        has_crash = False
        reasons = []
        
        for r in results:
            name = r.get("_name", "Unknown")
            can_buy = r.get("can_buy", False)
            risk = r.get("risk_level", "UNKNOWN")
            condition = r.get("market_condition", "")
            reason = r.get("reason", "")
            
            votes[name] = {
                "can_buy": can_buy,
                "risk_level": risk,
                "reason": reason[:100]
            }
            
            if can_buy:
                buy_votes += 1
            else:
                no_buy_votes += 1
            
            if condition == "CRASH":
                has_crash = True
                logger.warning(f"[MultiLLM] ⚠️ {name}이 CRASH 판정! 매수 차단.")
            
            reasons.append(f"{name}: {reason[:50]}")
        
        total_votes = buy_votes + no_buy_votes
        
        buy_ratio = (buy_votes / total_votes) if total_votes > 0 else 0.0

        # CRASH가 하나라도 있으면 무조건 차단 (정책으로 비활성화 가능)
        if has_crash and self.policy["crash_veto"]:
            consensus_result = {
                "risk_level": "HIGH",
                "can_buy": False,
                "market_condition": "CRASH",
                "reason": f"CRASH detected by LLM. {'; '.join(reasons)}",
                "consensus": f"CRASH_VETO ({buy_votes}/{total_votes} buy votes, but CRASH detected)",
                "votes": votes
            }
        # 비율 기반 합의
        elif buy_ratio > self.policy["required_buy_ratio"]:
            consensus_result = {
                "risk_level": "LOW",
                "can_buy": True,
                "market_condition": "BULLISH" if buy_votes == total_votes else "NEUTRAL",
                "reason": f"Buy ratio {buy_ratio:.2f} ({buy_votes}/{total_votes}). {'; '.join(reasons)}",
                "consensus": f"BUY_RATIO_OK ({buy_votes}/{total_votes}, threshold>{self.policy['required_buy_ratio']:.2f})",
                "votes": votes
            }
        elif buy_ratio == self.policy["required_buy_ratio"]:
            # 임계값 동률 처리
            tie_breaker = self.policy["tie_breaker"]
            if tie_breaker == "buy":
                final_buy = True
                consensus_type = "TIE_BUY (policy=buy)"
            elif tie_breaker == "hold":
                final_buy = False
                consensus_type = "TIE_HOLD (policy=hold)"
            else:
                # persona
                if persona == "aggressive":
                    final_buy = True
                    consensus_type = "TIE_BUY (persona=aggressive)"
                else:
                    final_buy = False
                    consensus_type = "TIE_HOLD (persona)"
            
            consensus_result = {
                "risk_level": "LOW" if final_buy else "HIGH",
                "can_buy": final_buy,
                "market_condition": "NEUTRAL",
                "reason": f"Threshold tie ratio {buy_ratio:.2f} ({buy_votes}/{total_votes}). {'; '.join(reasons)}",
                "consensus": consensus_type,
                "votes": votes
            }
        else:
            consensus_result = {
                "risk_level": "HIGH",
                "can_buy": False,
                "market_condition": "BEARISH",
                "reason": f"Buy ratio {buy_ratio:.2f} below threshold {self.policy['required_buy_ratio']:.2f}. {'; '.join(reasons)}",
                "consensus": f"HOLD_RATIO_BLOCK ({buy_votes}/{total_votes}, threshold>{self.policy['required_buy_ratio']:.2f})",
                "votes": votes
            }
        
        logger.info(f"[MultiLLM] 합의 결과: {consensus_result['consensus']} → can_buy={consensus_result['can_buy']}")
        try:
            _cache_put(_ck, consensus_result)
        except Exception:
            pass
        return consensus_result

    # === [v5.0 신규] 섹터 특화 뉴스 veto ===
    # 배경: 반도체 업종 전체가 무너지는 와중에도 "시장 전체" 판단만으로는 감지되지 않아
    # SOXL/SMH 등을 계속 물타기 매수한 사고(2026-07)를 막기 위한 전용 게이트.
    # 전체 합의(4-LLM) 대신 Gemini 단독으로 처리한다 — 종목마다 섹터 체크가 발생하므로
    # 4-LLM 합의로 처리하면 무료 API 쿼터가 감당 못할 정도로 소진된다. 대신 페르소나에
    # 흔들리지 않는 엄격한 전용 프롬프트(check_sector_crash)를 사용해 신뢰도를 보강한다.
    def fetch_sector_news(self, sector_key, query, lang="en"):
        """섹터 전용 뉴스 수집 (Gemini 담당, Google News RSS)."""
        gemini = self.analysts[0] if self.analysts else None
        if gemini is None or not hasattr(gemini, 'fetch_topic_news'):
            return ""
        try:
            return gemini.fetch_topic_news(query, lang=lang)
        except Exception as e:
            logger.error(f"[MultiLLM] 섹터 뉴스 수집 실패({sector_key}): {e}")
            return ""

    def check_sector_sentiment(self, sector_key, sector_label, news_text):
        """섹터 단위 크래시 판별 (30분 캐시). persona 인자를 받지 않는다 — 자본보호 전용
        게이트는 공격적 페르소나에도 완화되지 않아야 하기 때문."""
        if not news_text:
            return {"risk_level": "LOW", "can_buy": True, "market_condition": "NEUTRAL",
                     "reason": "No sector news, skipping.", "consensus": "N/A"}

        _ck = _cache_key(news_text, f"sector::{sector_key}")
        cached = _cache_get(_ck, store=_SECTOR_CACHE, ttl=_SECTOR_CACHE_TTL_SEC)
        if cached is not None:
            logger.info(f"[MultiLLM] 섹터 캐시 HIT ({sector_key})")
            return cached

        gemini = self.analysts[0] if self.analysts else None
        if gemini is None or not hasattr(gemini, 'check_sector_crash'):
            return {"risk_level": "LOW", "can_buy": True, "market_condition": "NEUTRAL",
                     "reason": "Sector check unavailable, defaulting to safe-pass.", "consensus": "N/A"}

        try:
            result = gemini.check_sector_crash(sector_label, news_text)
        except Exception as e:
            logger.error(f"[MultiLLM] 섹터 판별 실패({sector_key}): {e}")
            return {"risk_level": "LOW", "can_buy": True, "market_condition": "NEUTRAL",
                     "reason": f"Sector check error: {e}", "consensus": "ERROR_SAFE_PASS"}

        result["consensus"] = f"SECTOR:{sector_key}"
        if result.get("market_condition") == "CRASH":
            logger.warning(f"[MultiLLM] ⚠️ 섹터 CRASH 감지: {sector_label} - {result.get('reason', 'N/A')}")
        try:
            _cache_put(_ck, result, store=_SECTOR_CACHE)
        except Exception:
            pass
        return result
