
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from app.use_cases.signal_service import get_signal_service

def test_to_vote_three_state_neutral():
    """Verify that 'neutral' regime (HMM/BCD) results in exactly 0.0 vote."""
    svc = get_signal_service()
    
    with patch("app.use_cases.signal_service._spectrum.calculate") as mock_calc:
        with patch("app.use_cases.signal_service.get_bcd_service") as mock_bcd, \
             patch("app.use_cases.signal_service.get_market_repository") as mock_repo, \
             patch("app.use_cases.signal_service.get_ai_service"), \
             patch("app.use_cases.signal_service.get_ema_service"), \
             patch("app.use_cases.signal_service.get_narrative_service"), \
             patch("app.use_cases.signal_service._safe_hmm_states", return_value=(None, None)), \
             patch("app.use_cases.signal_service._safe_ai_cross", return_value=("neutral", 50.0)):
            
            # Setup BCD as neutral
            mock_bcd.return_value.get_regime_with_posterior.return_value = ("Neutral Regime", "neutral", 0.95)
            
            # Setup mock data
            # Use 100 rows to be safe for TA indicators
            df = pd.DataFrame({
                "Open": [70000.0]*100, "High": [71000.0]*100, "Low": [69000.0]*100, "Close": [70000.0]*100, "Volume": [1000.0]*100
            })
            mock_repo.return_value.get_ohlcv_with_metrics.return_value = df
            mock_repo.return_value.get_latest_metrics.return_value = {}

            # Run signal logic
            svc.get_signal()
            
            # Verify l1_vote in spectrum.calculate call
            assert mock_calc.called, "DirectionalSpectrum.calculate was not called"
            call_kwargs = mock_calc.call_args.kwargs
            l1_vote = call_kwargs.get("l1_vote")
            
            assert l1_vote == 0.0, f"Neutral regime should result in 0.0 vote, got {l1_vote}"

def test_to_vote_three_state_bull_bear():
    """Verify bull/bear still produce directional votes."""
    svc = get_signal_service()
    
    with patch("app.use_cases.signal_service._spectrum.calculate") as mock_calc:
        with patch("app.use_cases.signal_service.get_market_repository") as mock_repo, \
             patch("app.use_cases.signal_service.get_ai_service"), \
             patch("app.use_cases.signal_service.get_ema_service"), \
             patch("app.use_cases.signal_service.get_narrative_service"), \
             patch("app.use_cases.signal_service._safe_hmm_states", return_value=(None, None)):
            
            # 1. BULL Case
            with patch("app.use_cases.signal_service.get_bcd_service") as mock_bcd, \
                 patch("app.use_cases.signal_service._safe_ai_cross", return_value=("bull", 100.0)):
                
                mock_bcd.return_value.get_regime_with_posterior.return_value = ("Bullish", "bull", 1.0)
                df = pd.DataFrame({"Open": [70000.0]*100, "High": [71000.0]*100, "Low": [69000.0]*100, "Close": [70000.0]*100, "Volume": [1000.0]*100})
                mock_repo.return_value.get_ohlcv_with_metrics.return_value = df
                mock_repo.return_value.get_latest_metrics.return_value = {}
                
                svc.get_signal()
                assert mock_calc.called
                assert mock_calc.call_args.kwargs.get("l1_vote") >= 0.25 

            # 2. BEAR Case
            mock_calc.reset_mock()
            with patch("app.use_cases.signal_service.get_bcd_service") as mock_bcd, \
                 patch("app.use_cases.signal_service._safe_ai_cross", return_value=("bear", 80.0)):
                
                mock_bcd.return_value.get_regime_with_posterior.return_value = ("Bearish", "bear", 0.90)
                df = pd.DataFrame({"Open": [70000.0]*100, "High": [71000.0]*100, "Low": [69000.0]*100, "Close": [70000.0]*100, "Volume": [1000.0]*100})
                mock_repo.return_value.get_ohlcv_with_metrics.return_value = df
                
                svc.get_signal()
                assert mock_calc.called
                assert mock_calc.call_args.kwargs.get("l1_vote") == -0.90
