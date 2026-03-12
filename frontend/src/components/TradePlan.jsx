const STATUS_CONFIG = {
    ACTIVE: {
        bg: "#dcfce7",
        border: "#16a34a",
        color: "#15803d",
        icon: "✦",
        label: "ACTIVE — Trade when price enters entry zone",
    },
    ADVISORY: {
        bg: "#fef9c3",
        border: "#d97706",
        color: "#92400e",
        icon: "⚠",
        label: "ADVISORY — Reduce size and wait for confirmation",
    },
    SUSPENDED: {
        bg: "#fee2e2",
        border: "#dc2626",
        color: "#991b1b",
        icon: "✕",
        label: "SUSPENDED — Do not trade this signal",
    },
};

function TradeRow({ label, value, type }) {
    return (
        <div className="trade-row">
            <span className="trade-label">{label}</span>
            <span className={`trade-value ${type ? `trade-${type}` : ""}`}>{value}</span>
        </div>
    );
}

export default function TradePlan({ plan }) {
    const {
        action,
        entry_start,
        entry_end,
        sl,
        tp1,
        tp2,
        leverage,
        position_size,
        status = "SUSPENDED",
        status_reason = "",
    } = plan;

    const isBull  = action === "LONG";
    const cfg     = STATUS_CONFIG[status] ?? STATUS_CONFIG.SUSPENDED;
    const dimmed  = status === "SUSPENDED";

    const actionColor =
        dimmed    ? "#9ca3af"
        : isBull  ? "#16a34a"
        : "#dc2626";

    const fmt = (v) =>
        `$${v.toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        })}`;

    return (
        <div className="card">
            <div className="section-title">Trade Plan · Execution</div>

            {/* ── Execution gate banner ── */}
            <div style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "7px 12px",
                marginBottom: 14,
                borderRadius: 6,
                background: cfg.bg,
                border: `1px solid ${cfg.border}`,
                color: cfg.color,
                fontSize: 11.5,
                fontWeight: 600,
            }}>
                <span style={{ fontSize: 13 }}>{cfg.icon}</span>
                <span>{cfg.label}</span>
            </div>

            {/* ── Action header ── */}
            <div style={{
                textAlign: "center",
                marginBottom: 14,
                opacity: dimmed ? 0.4 : 1,
                transition: "opacity 0.2s",
            }}>
                <div style={{
                    fontFamily: "JetBrains Mono, monospace",
                    fontSize: 32,
                    fontWeight: 800,
                    color: actionColor,
                }}>
                    {action}
                </div>
                <div style={{ fontSize: 11, color: "#6b7280", marginTop: 2 }}>
                    BTC/USDT Perpetual · Limit Order
                </div>
            </div>

            {/* ── Trade rows ── */}
            <div style={{ opacity: dimmed ? 0.4 : 1, transition: "opacity 0.2s" }}>
                <TradeRow
                    label="Entry Zone"
                    value={`${fmt(entry_start)} – ${fmt(entry_end)}`}
                />
                <TradeRow
                    label="Stop Loss (SL)"
                    value={fmt(sl)}
                    type={isBull ? "bear" : "bull"}
                />
                <TradeRow
                    label="Take Profit 1 (1:1.5)"
                    value={fmt(tp1)}
                    type={isBull ? "bull" : "bear"}
                />
                <TradeRow
                    label="Take Profit 2 (1:2.5)"
                    value={fmt(tp2)}
                    type={isBull ? "bull" : "bear"}
                />
                <TradeRow label="Max Leverage"   value={`${leverage}x`} />
                <TradeRow label="Position Size"  value={position_size} />
            </div>

            {/* ── Status reason ── */}
            {status_reason && (
                <div style={{
                    marginTop: 12,
                    padding: "6px 10px",
                    background: "#f9fafb",
                    borderLeft: `3px solid ${cfg.border}`,
                    fontSize: 11,
                    color: "#6b7280",
                    lineHeight: 1.6,
                }}>
                    {status_reason}
                </div>
            )}
        </div>
    );
}
