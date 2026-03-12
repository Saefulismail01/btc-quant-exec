import { useSignal } from "../hooks/useSignal";
import { usePrice } from "../hooks/usePrice";
import Navbar from "../components/Navbar";
import MetricCard from "../components/MetricCard";
import ConfluenceBar from "../components/ConfluenceBar";
import MarketSnapshot from "../components/MarketSnapshot";
import TradePlan from "../components/TradePlan";
import LayerList from "../components/LayerList";
import ConclusionCard from "../components/ConclusionCard";

function fmt(v) {
    return v != null ? `$${Number(v).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}` : "—";
}

export default function Dashboard() {
    const { data, loading, error, lastUpdated, refresh } = useSignal(60000);
    const { price: livePrice } = usePrice(3000); // Update every 3 seconds

    const displayPrice = livePrice || data?.price?.now;

    const isBull = data?.trend?.short === "BULL";

    return (
        <div className="app-root">
            <Navbar lastUpdated={lastUpdated} onRefresh={refresh} loading={loading} />

            <main className="main-content">
                {error && (
                    <div className="alert-error">
                        ⚠ {error} — Is the FastAPI backend running?
                    </div>
                )}

                {loading && !data && (
                    <div className="loading-bar">Loading signal data…</div>
                )}

                {data && (
                    <>
                        {/* ── Metric cards ── */}
                        <div className="metrics-row">
                            <MetricCard
                                label="BTC / USDT"
                                value={fmt(displayPrice)}
                                delta="Live Price"
                                deltaType="neutral"
                            />
                            <MetricCard
                                label="Market Trend"
                                value={data.trend.short}
                                delta={`${isBull ? "▲" : "▼"} ${data.trend.bias}`}
                                deltaType={isBull ? "bull" : "bear"}
                            />
                            <MetricCard
                                label="Funding Rate"
                                value={data.market_metrics.funding_rate.toFixed(8)}
                                delta={data.market_metrics.funding_label}
                                deltaType={
                                    data.market_metrics.funding_rate > 0.0001 ? "bear" :
                                        data.market_metrics.funding_rate < -0.0001 ? "bull" : "neutral"
                                }
                            />
                            <MetricCard
                                label="Open Interest"
                                value={`${data.market_metrics.open_interest.toLocaleString(undefined, { maximumFractionDigits: 0 })} BTC`}
                                delta="BTC Perpetual"
                                deltaType="neutral"
                            />
                            <MetricCard
                                label="Max Leverage"
                                value={`${data.trade_plan.leverage}x`}
                                delta={`Vol: ${data.volatility.label} (${(data.volatility.ratio * 100).toFixed(2)}%)`}
                                deltaType={data.volatility.label === "High" ? "bear" : "bull"}
                            />
                        </div>

                        {/* ── Confluence bar ── */}
                        <ConfluenceBar
                            confluence={data.confluence}
                            action={data.trade_plan.action}
                        />

                        {/* ── Main two-column panel ── */}
                        <div className="main-panel">
                            {/* Left column */}
                            <div className="panel-left">
                                <MarketSnapshot price={data.price} metrics={data.market_metrics} />
                                <div className="card">
                                    <div className="section-title">Trend Analysis — Layer 2</div>
                                    {[
                                        ["Trend Bias", data.trend.bias],
                                        ["EMA Structure", data.trend.ema_structure],
                                        ["Momentum", data.trend.momentum],
                                    ].map(([label, value]) => (
                                        <div className="snap-row" key={label}>
                                            <span className="snap-label">{label}</span>
                                            <span className="snap-value" style={{ fontSize: 12 }}>{value}</span>
                                        </div>
                                    ))}
                                </div>
                                <LayerList layers={data.confluence.layers} trend={data.trend.short} />
                            </div>

                            {/* Right column */}
                            <div className="panel-right">
                                <TradePlan plan={data.trade_plan} />
                                <ConclusionCard confluence={data.confluence} validityUtc={data.validity_utc} />
                                <div className="card" style={{ padding: "10px 16px" }}>
                                    <div className="section-title">Data Sources</div>
                                    <div style={{ fontSize: 11.5, color: "#374151", lineHeight: 1.8 }}>
                                        📡 <strong>Binance API</strong> → DuckDB (<code>btc-quant.db</code>)<br />
                                        🧠 <strong>BCD Regime</strong>: Active (Layer 1)<br />
                                        🤖 <strong>AI MLP Signal</strong>: Active (Layer 3)<br />
                                        📊 <strong>Sentiment</strong>: Pending Integration
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* ── Footer ── */}
                        <footer className="footer-bar">
                            BTC-QUANT v2.1 · FastAPI + React · Live Data<br />
                            Last refresh: <strong>{lastUpdated?.toUTCString().replace("GMT", "UTC") ?? "—"}</strong>
                        </footer>
                    </>
                )}
            </main>
        </div>
    );
}
