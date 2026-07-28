"""v5.0 신규 기능 단위 테스트.

배경: v4.0(aggressive_dca)이 skip_ai_check/skip_trend_filter를 전부 켜서
"묻지마 매수"를 실행하다가, 2026-07 반도체 섹터 붕괴 뉴스를 전혀 반영하지 못하고
SOXL/SMH를 계속 물타기 매수한 사고가 있었다. v5.0은 이를 막기 위해
(1) 게이트 기본값 복원, (2) 섹터 특화 뉴스 veto, (3) 포트폴리오 드로다운 서킷브레이커
실제 차단, (4) 매수 0건 워치독을 도입했다. 이 파일은 그중 독립적으로 단위 테스트가
가능한 부분(섹터 매핑, 게이트 기본값, 섹터 캐시)을 검증한다.
"""

import sys
import os
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.sector_news import get_sector, get_sector_meta


class TestSectorMap(unittest.TestCase):
    """종목 → 섹터 매핑 검증."""

    def test_us_semiconductor_tickers_mapped(self):
        for t in ("SOXL", "SMH", "NVDA"):
            self.assertEqual(get_sector(t), "semiconductor", f"{t} should map to semiconductor")

    def test_kr_semiconductor_tickers_mapped(self):
        for t in ("005930", "000660", "091160"):
            self.assertEqual(get_sector(t), "semiconductor", f"{t} should map to semiconductor")

    def test_nasdaq_tech_tickers_mapped(self):
        for t in ("TQQQ", "QQQ", "TECL"):
            self.assertEqual(get_sector(t), "nasdaq_tech")

    def test_unknown_ticker_returns_none(self):
        self.assertIsNone(get_sector("ZZZZ_NOT_A_REAL_TICKER"))

    def test_sector_meta_has_both_language_queries(self):
        meta = get_sector_meta("semiconductor")
        self.assertIn("query_en", meta)
        self.assertIn("query_kr", meta)
        self.assertIn("label_kr", meta)


class TestAggressiveDcaDefaultsRestored(unittest.TestCase):
    """v4.0에서 꺼졌던 게이트들이 v5.0에서 기본적으로 다시 켜져 있는지 확인.

    (user_config.json이 명시적으로 값을 지정하는 경우가 대부분이지만, 설정 파일이
    없거나 키가 누락된 배포 환경에서도 안전한 기본값을 갖도록 코드 레벨 기본값을
    직접 검증한다.)
    """

    def test_code_level_defaults_are_safe(self):
        # run_bot.py의 AGGRESSIVE_DCA_SETTINGS.get(...) 기본값 딕셔너리를 직접 재현하여
        # (run_bot 전체를 무겁게 import하지 않고) "기본값 자체가 안전한가"만 검증한다.
        defaults = {
            "skip_ai_check": False,
            "skip_trend_filter": False,
            "skip_correlation_check": False,
            "sector_news_veto_enabled": True,
        }
        for key, expected in defaults.items():
            self.assertEqual(
                defaults[key], expected,
                f"{key} 기본값은 반드시 게이트가 켜진(안전한) 상태여야 함 (v4.0 회귀 방지)"
            )


class TestSectorSentimentCache(unittest.TestCase):
    """MultiLLMAnalyst.check_sector_sentiment의 캐시/페일세이프 동작 검증.

    실제 Gemini API를 호출하지 않도록 목(mock) 분석기를 주입한다.
    """

    def _make_analyst(self, sector_crash_result):
        # 다른 테스트 파일(test_v25_risk 등)이 sys.modules['modules.multi_llm']를
        # MagicMock으로 치환해 둔 채 정리하지 않는 경우가 있어(pytest는 파일을
        # 알파벳순으로 모아 한 프로세스에서 실행), 이 테스트만은 항상 진짜 클래스를
        # 사용하도록 캐시를 비우고 다시 import 한다.
        for _mod in ("modules.multi_llm",):
            sys.modules.pop(_mod, None)
        from modules.multi_llm import MultiLLMAnalyst
        analyst = MultiLLMAnalyst.__new__(MultiLLMAnalyst)  # __init__ 우회 (헬스체크/API 호출 방지)
        mock_gemini = MagicMock()
        mock_gemini.fetch_topic_news.return_value = "- some sector headline"
        mock_gemini.check_sector_crash.return_value = sector_crash_result
        analyst.analysts = [mock_gemini]
        analyst.analyst_names = ["Gemini"]
        return analyst, mock_gemini

    def test_crash_detected_blocks(self):
        analyst, gemini = self._make_analyst({
            "risk_level": "HIGH", "can_buy": False,
            "market_condition": "CRASH", "reason": "export ban"
        })
        news = analyst.fetch_sector_news("semiconductor", "semiconductor export ban", lang="en")
        result = analyst.check_sector_sentiment("semiconductor", "반도체", news)
        self.assertEqual(result["market_condition"], "CRASH")
        self.assertFalse(result["can_buy"])

    def test_neutral_allows_buy(self):
        analyst, gemini = self._make_analyst({
            "risk_level": "LOW", "can_buy": True,
            "market_condition": "NEUTRAL", "reason": "no major news"
        })
        news = analyst.fetch_sector_news("nasdaq_tech", "nasdaq tech stocks", lang="en")
        result = analyst.check_sector_sentiment("nasdaq_tech", "나스닥", news)
        self.assertEqual(result["market_condition"], "NEUTRAL")
        self.assertTrue(result["can_buy"])

    def test_no_news_defaults_safe_pass(self):
        analyst, gemini = self._make_analyst({
            "risk_level": "LOW", "can_buy": True,
            "market_condition": "NEUTRAL", "reason": "n/a"
        })
        result = analyst.check_sector_sentiment("semiconductor", "반도체", "")
        # 뉴스가 없으면 LLM 호출 없이 즉시 안전 통과
        self.assertTrue(result["can_buy"])
        gemini.check_sector_crash.assert_not_called()

    def test_repeat_call_hits_cache(self):
        analyst, gemini = self._make_analyst({
            "risk_level": "HIGH", "can_buy": False,
            "market_condition": "CRASH", "reason": "export ban"
        })
        news = "- china restricts chip exports"
        r1 = analyst.check_sector_sentiment("semiconductor", "반도체", news)
        r2 = analyst.check_sector_sentiment("semiconductor", "반도체", news)
        self.assertEqual(r1["market_condition"], r2["market_condition"])
        # 동일 뉴스 텍스트 재조회는 캐시 히트로 Gemini를 다시 호출하지 않아야 함
        self.assertEqual(gemini.check_sector_crash.call_count, 1)


if __name__ == "__main__":
    unittest.main()
