import { usePaperTrade } from "../hooks/usePaperTrade";
import { usePrice } from "../hooks/usePrice";
import Navbar from "../components/Navbar";
import {
    AreaChart, Area, BarChart, Bar,
    XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine
} from "recharts";

const fmt = (v) => `$${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const fmtPnl = (v) => {
    const n = Number(v);
    return (n >= 0 ? "+" : "") + fmt(n);
};

function StatCard({ label, value, sub, type = "neutral" }) {
    const color = type === "bull" ? "#16a34a" : type === "bear" ? "#dc2626" : "#1a1d23";
    return (
        <div className="metric-card">
            <div className="metric-label">{label}</div>
            <div className="metric-value" style={{ color, fontSize: 18 }}>{value}</div>
            {sub && <div className="metric-delta delta-neutral">{sub}</div>}
        </div>
    );
}

function OpenPositionCard({ pos, livePrice }) {
    if (!pos) {
        return (
            <div className="card" style={{ textAlign: "center", padding: "28px 20px", color: "#9ca3af" }}>
                <div style={{ fontSize: 28, marginBottom: 8 }}>⏸</div>
                <div style={{ fontWeight: 600, fontSize: 13 }}>No Active Position</div>
                <div style={{ fontSize: 11, marginTop: 4 }}>Waiting for next ACTIVE signal</div>
            </div>
        );
    }

    const isLong = pos.side === "LONG";
    const unrealizedPnl = livePrice
        ? isLong
            ? (livePrice - pos.entry_price) * pos.size_base
            : (pos.entry_price - livePrice) * pos.size_base
        : null;
    const unrealizedPct = unrealizedPnl !== null && pos.size_quote
        ? (unrealizedPnl / pos.size_quote) * 100
        : null;
    const isProfitable = unrealizedPnl !== null ? unrealizedPnl >= 0 : null;

    return (
        <div className="card" style={{ borderLeft: `3px solid ${isLong ? "#16a34a" : "#dc2626"}` }}>
            <div className="section-title">Open Position</div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                <span className={`badge ${isLong ? "badge-bull" : "badge-bear"}`} style={{ fontSize: 12, padding: "4px 12px" }}>
                    {pos.side}
                </span>
                {unrealizedPnl !== null && (
                    <span style={{ fontFamily: "JetBrains Mono, monospace", fontWeight: 700, fontSize: 16, color: isProfitable ? "#16a34a" : "#dc2626" }}>
                        {fmtPnl(unrealizedPnl.toFixed(2))}
                        <span style={{ fontSize: 11, fontWeight: 400, marginLeft: 4 }}>
                            ({unrealizedPct >= 0 ? "+" : ""}{unrealizedPct?.toFixed(2)}%)
                        </span>
                    </span>
                )}
            </div>
            {[
                ["Entry Price", fmt(pos.entry_price)],
                ["Live Price", livePrice ? fmt(livePrice) : "—"],
                ["Stop Loss", fmt(pos.sl)],
                ["Take Profit", fmt(pos.tp)],
                ["Size", `${fmt(pos.size_quote)} USDT`],
            ].map(([label, value]) => (
                <div className="snap-row" key={label}>
                    <span className="snap-label">{label}</span>
                    <span className="snap-value">{value}</span>
                </div>
            ))}
        </div>
    );
}

function EquityCurveChart({ data }) {
    if (!data || data.length === 0) {
        return (
            <div className="card">
                <div className="section-title">Equity Curve</div>
                <div style={{ textAlign: "center", padding: "40px 0", color: "#9ca3af", fontSize: 13 }}>
                    No closed trades yet
                </div>
            </div>
        );
    }

    const min = Math.min(...data.map(d => d.balance));
    const max = Math.max(...data.map(d => d.balance));
    const isPositive = data[data.length - 1]?.balance >= 10000;

    return (
        <div className="card">
            <div className="section-title">Equity Curve</div>
            <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                    <defs>
                        <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor={isPositive ? "#16a34a" : "#dc2626"} stopOpacity={0.15} />
                            <stop offset="95%" stopColor={isPositive ? "#16a34a" : "#dc2626"} stopOpacity={0} />
                        </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                    <XAxis dataKey="trade" tick={{ fontSize: 10 }} label={{ value: "Trade #", position: "insideBottom", offset: -2, fontSize: 10 }} />
                    <YAxis domain={[min * 0.998, max * 1.002]} tick={{ fontSize: 10 }}
                        tickFormatter={(v) => `$${(v / 1000).toFixed(1)}k`} width={55} />
                    <Tooltip
                        formatter={(v) => [fmt(v), "Balance"]}
                        labelFormatter={(l) => `Trade #${l}`}
                        contentStyle={{ fontSize: 12, borderRadius: 6 }}
                    />
                    <ReferenceLine y={10000} stroke="#9ca3af" strokeDasharray="4 2" />
                    <Area type="monotone" dataKey="balance" stroke={isPositive ? "#16a34a" : "#dc2626"}
                        strokeWidth={2} fill="url(#eqGrad)" dot={false} />
                </AreaChart>
            </ResponsiveContainer>
        </div>
    );
}

function PnlBarChart({ data }) {
    if (!data || data.length === 0) return null;
    return (
        <div className="card">
            <div className="section-title">PnL Per Trade</div>
            <ResponsiveContainer width="100%" height={160}>
                <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" vertical={false} />
                    <XAxis dataKey="trade" tick={{ fontSize: 10 }} />
                    <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => `$${v}`} width={55} />
                    <Tooltip
                        formatter={(v) => [fmtPnl(v), "PnL"]}
                        labelFormatter={(l) => `Trade #${l}`}
                        contentStyle={{ fontSize: 12, borderRadius: 6 }}
                    />
                    <ReferenceLine y={0} stroke="#9ca3af" />
                    <Bar dataKey="pnl" radius={[3, 3, 0, 0]}
                        fill="#16a34a"
                        label={false}
                        isAnimationActive={true}
                        // Color each bar individually
                        cells={data.map((entry, i) => (
                            <rect key={i} fill={entry.pnl >= 0 ? "#16a34a" : "#dc2626"} />
                        ))}
                    />
                </BarChart>
            </ResponsiveContainer>
        </div>
    );
}

function TradeHistoryTable({ history }) {
    const sorted = [...history].sort((a, b) => b.timestamp - a.timestamp);

    return (
        <div className="card">
            <div className="section-title">Trade History ({history.length} trades)</div>
            <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                    <thead>
                        <tr style={{ borderBottom: "2px solid #f3f4f6" }}>
                            {["Time", "Side", "Entry", "Exit", "PnL (USDT)", "PnL %", "Status"].map(h => (
                                <th key={h} style={{ textAlign: "left", padding: "6px 8px", color: "#6b7280", fontWeight: 600, fontSize: 10, textTransform: "uppercase", letterSpacing: "0.8px", whiteSpace: "nowrap" }}>
                                    {h}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {sorted.length === 0 ? (
                            <tr>
                                <td colSpan={7} style={{ textAlign: "center", padding: "32px 0", color: "#9ca3af" }}>
                                    No trades yet
                                </td>
                            </tr>
                        ) : sorted.map((t) => {
                            const isProfit = (t.pnl || 0) >= 0;
                            const isOpen = t.status === "OPEN";
                            const pnlColor = isOpen ? "#6b7280" : isProfit ? "#16a34a" : "#dc2626";
                            return (
                                <tr key={t.id} style={{ borderBottom: "1px solid #f9fafb" }}>
                                    <td style={{ padding: "7px 8px", color: "#6b7280", fontFamily: "monospace", whiteSpace: "nowrap" }}>
                                        {new Date(t.timestamp).toLocaleDateString("en-GB", { month: "short", day: "numeric" })}
                                        {" "}
                                        {new Date(t.timestamp).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}
                                    </td>
                                    <td style={{ padding: "7px 8px" }}>
                                        <span className={`badge ${t.side === "LONG" ? "badge-bull" : "badge-bear"}`}>
                                            {t.side}
                                        </span>
                                    </td>
                                    <td style={{ padding: "7px 8px", fontFamily: "monospace", fontWeight: 600 }}>
                                        {fmt(t.entry_price)}
                                    </td>
                                    <td style={{ padding: "7px 8px", fontFamily: "monospace", color: "#6b7280" }}>
                                        {t.exit_price ? fmt(t.exit_price) : "—"}
                                    </td>
                                    <td style={{ padding: "7px 8px", fontFamily: "monospace", fontWeight: 700, color: pnlColor }}>
                                        {isOpen ? "—" : fmtPnl((t.pnl || 0).toFixed(2))}
                                    </td>
                                    <td style={{ padding: "7px 8px", fontFamily: "monospace", color: pnlColor }}>
                                        {isOpen ? "—" : `${(t.pnl_pct || 0) >= 0 ? "+" : ""}${(t.pnl_pct || 0).toFixed(2)}%`}
                                    </td>
                                    <td style={{ padding: "7px 8px" }}>
                                        <span style={{
                                            display: "inline-block", padding: "2px 8px", borderRadius: 20,
                                            fontSize: 10, fontWeight: 600,
                                            background: isOpen ? "#dbeafe" : isProfit ? "#dcfce7" : "#fee2e2",
                                            color: isOpen ? "#1d4ed8" : isProfit ? "#15803d" : "#b91c1c",
                                        }}>
                                            {t.status}
                                        </span>
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

export default function PaperTrade() {
    const { status, history, equityCurve, stats, loading, error, resetting, refresh, reset } = usePaperTrade(10000);
    const { price: livePrice } = usePrice();

    const pnlType = parseFloat(stats.totalPnl) >= 0 ? "bull" : "bear";

    return (
        <div className="app-root">
            <Navbar
                lastUpdated={null}
                onRefresh={refresh}
                loading={loading}
                extraContent={
                    <button
                        className="btn-refresh"
                        onClick={reset}
                        disabled={resetting}
                        style={{ color: "#dc2626", borderColor: "#fecaca" }}
                    >
                        {resetting ? "Resetting…" : "⚠ Reset Account"}
                    </button>
                }
            />

            <main className="main-content" style={{ paddingTop: 16 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
                    <span style={{ fontSize: 20 }}>📋</span>
                    <div>
                        <div style={{ fontWeight: 700, fontSize: 16 }}>Paper Trading Dashboard</div>
                        <div style={{ fontSize: 11, color: "#6b7280" }}>Virtual account · BTC/USDT Perpetual · Auto-updates every 10s</div>
                    </div>
                </div>

                {error && (
                    <div className="alert-error">⚠ {error}</div>
                )}

                {loading && !status ? (
                    <div className="loading-bar">Loading paper trade data…</div>
                ) : (
                    <>
                        {/* Summary stats */}
                        <div className="metrics-row" style={{ gridTemplateColumns: "repeat(5, 1fr)" }}>
                            <StatCard label="Balance" value={`$${Number(stats.currentBalance).toLocaleString()}`} sub="Current equity" />
                            <StatCard
                                label="Total PnL"
                                value={fmtPnl(stats.totalPnl)}
                                sub={`${stats.totalPnlPct >= 0 ? "+" : ""}${stats.totalPnlPct}% from $10,000`}
                                type={pnlType}
                            />
                            <StatCard label="Win Rate" value={`${stats.winRate}%`} sub={`${stats.wins}W / ${stats.losses}L`} type={parseFloat(stats.winRate) >= 50 ? "bull" : "bear"} />
                            <StatCard label="Total Trades" value={stats.totalTrades} sub="Closed positions" />
                            <StatCard label="Open Position" value={status?.active_position ? status.active_position.side : "None"}
                                sub={status?.active_position ? `Entry: ${fmt(status.active_position.entry_price)}` : "Waiting for signal"}
                                type={status?.active_position?.side === "LONG" ? "bull" : status?.active_position?.side === "SHORT" ? "bear" : "neutral"}
                            />
                        </div>

                        {/* Main grid */}
                        <div className="main-panel">
                            <div className="panel-left">
                                <EquityCurveChart data={equityCurve} />
                                <PnlBarChart data={equityCurve} />
                            </div>
                            <div className="panel-right">
                                <OpenPositionCard pos={status?.active_position} livePrice={livePrice} />
                                <div className="card" style={{ padding: "10px 16px" }}>
                                    <div className="section-title">Account Info</div>
                                    {[
                                        ["Initial Balance", "$10,000.00"],
                                        ["Current Balance", fmt(stats.currentBalance)],
                                        ["Equity", fmt(status?.account?.equity ?? stats.currentBalance)],
                                        ["Last Update", status?.account?.last_update
                                            ? new Date(status.account.last_update).toLocaleTimeString("en-GB")
                                            : "—"],
                                    ].map(([label, value]) => (
                                        <div className="snap-row" key={label}>
                                            <span className="snap-label">{label}</span>
                                            <span className="snap-value">{value}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>

                        <TradeHistoryTable history={history} />

                        <footer className="footer-bar">
                            BTC-QUANT Paper Trading · Virtual execution only · Not financial advice
                        </footer>
                    </>
                )}
            </main>
        </div>
    );
}
