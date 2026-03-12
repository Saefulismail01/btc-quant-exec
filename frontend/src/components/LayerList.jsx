function ContribBar({ value }) {
    // value: -1.0 to +1.0
    const pct = Math.abs(value) * 100;
    const isBull = value >= 0;
    const color = value > 0.1 ? "#16a34a" : value < -0.1 ? "#dc2626" : "#d97706";
    const side = isBull ? "bullish" : "bearish";
    return (
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 4 }}>
            <div style={{
                flex: 1, height: 6, background: "#f3f4f6", borderRadius: 4, overflow: "hidden"
            }}>
                <div style={{
                    width: `${pct}%`, height: "100%",
                    background: color, borderRadius: 4,
                    transition: "width 0.4s ease"
                }} />
            </div>
            <span style={{ fontSize: 10, fontFamily: "monospace", color, minWidth: 80 }}>
                {value > 0 ? "+" : ""}{(value * 100).toFixed(1)}% {side}
            </span>
        </div>
    );
}

function LayerRow({ icon, name, label, badgeCls, detail, aligned, contribution }) {
    return (
        <div className="layer-row" style={{ flexDirection: "column", alignItems: "flex-start", gap: 2, padding: "8px 0", borderBottom: "1px solid #f3f4f6" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, width: "100%" }}>
                <span style={{ fontSize: 13, color: aligned ? "#16a34a" : "#9ca3af" }}>{icon}</span>
                <span className="layer-name" style={{ fontWeight: 600, flex: 1 }}>{name}</span>
                <span className={`badge ${badgeCls}`}>{aligned ? "✓ ALIGNED" : "✗ NOT ALIGNED"}</span>
            </div>
            <div style={{ paddingLeft: 22, width: "100%" }}>
                <div style={{ fontSize: 11.5, color: "#374151", fontWeight: 500 }}>{label}</div>
                {detail && detail !== "BCD Model" && detail !== "MLP Model" && detail !== "ATR-based SL" && (
                    <div style={{ fontSize: 10.5, color: "#6b7280", marginTop: 1 }}>{detail}</div>
                )}
                {contribution !== undefined && (
                    <ContribBar value={contribution} />
                )}
            </div>
        </div>
    );
}

export default function LayerList({ layers, trend }) {
    const isBull = trend === "BULL";

    const l1 = layers.l1_hmm;
    const l2 = layers.l2_tech;
    const l3 = layers.l3_ai;
    const l4 = layers.l4_risk;

    const l1Badge = l1.aligned ? (isBull ? "badge-bull" : "badge-bear") : "badge-neutral";
    const l2Badge = l2.aligned ? (isBull ? "badge-bull" : "badge-bear") : "badge-neutral";
    const l3Badge = l3.aligned ? "badge-active" : "badge-neutral";
    const l4Badge = l4.aligned ? "badge-bull" : "badge-bear";

    return (
        <div className="card">
            <div className="section-title">Layer Confluence — Individual Decisions</div>
            <LayerRow
                icon="🧠" name="Layer 1 · BCD Regime"
                label={l1.label} badgeCls={l1Badge}
                detail={l1.detail} aligned={l1.aligned}
                contribution={l1.contribution}
            />
            <LayerRow
                icon="📈" name="Layer 2 · EMA Technical"
                label={l2.label} badgeCls={l2Badge}
                detail={l2.detail} aligned={l2.aligned}
                contribution={l2.contribution}
            />
            <LayerRow
                icon="🤖" name="Layer 3 · AI / MLP Signal"
                label={l3.label} badgeCls={l3Badge}
                detail={l3.detail} aligned={l3.aligned}
                contribution={l3.contribution}
            />
            <LayerRow
                icon="🛡️" name="Layer 4 · Volatility Risk"
                label={l4.label} badgeCls={l4Badge}
                detail={l4.detail} aligned={l4.aligned}
                contribution={l4.contribution}
            />
        </div>
    );
}
