import sys
from pathlib import Path
import json

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.services.signal_service import get_signal_service

def test_fgi_fields():
    svc = get_signal_service()
    sig = svc.get_signal()
    
    print("\n--- FGI Verification ---")
    print(f"FGI Score: {sig.market_metrics.fgi_score}")
    print(f"FGI Label: {sig.market_metrics.fgi_label}")
    print(f"Sentiment Adjustment: {sig.sentiment_adjustment}")
    print(f"Position Size String: {sig.trade_plan.position_size}")
    
    assert hasattr(sig.market_metrics, "fgi_score"), "Missing fgi_score in market_metrics"
    assert hasattr(sig, "sentiment_adjustment"), "Missing sentiment_adjustment in root"
    
    if sig.market_metrics.fgi_score > 80 or (sig.market_metrics.fgi_score < 20 and sig.trade_plan.action == "LONG"):
        assert sig.sentiment_adjustment == 0.75, f"Adjustment should be 0.75 for score {sig.market_metrics.fgi_score}"
    else:
        assert sig.sentiment_adjustment == 1.0, f"Adjustment should be 1.0 for score {sig.market_metrics.fgi_score}"
        
    print("\n✅ FGI Logic Verified Successfully.")

if __name__ == "__main__":
    try:
        test_fgi_fields()
    except Exception as e:
        print(f"\n❌ Verification Failed: {e}")
        sys.exit(1)
