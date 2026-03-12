export default function ConfluenceBar({ confluence, action }) {
    const { aligned_count, total, probability } = confluence;
    const isBull = action === "LONG";
    const scoreColor = probability === "high" ? "#16a34a" : probability === "med" ? "#d97706" : "#dc2626";
    const scoreLabel =
        probability === "high" ? `✓ ${aligned_count}/${total} Layers Aligned`
            : probability === "med" ? `◎ ${aligned_count}/${total} Layers Aligned`
                : `✗ ${aligned_count}/${total} Layers Aligned`;

    return (
        <div className="conf-bar">
            <span className="conf-title">Confluence Score</span>
            <span className={`badge badge-${isBull ? "bull" : "bear"}`} style={{ fontSize: 12, padding: "4px 12px" }}>
                {action} BIAS
            </span>
            <span style={{ fontFamily: "JetBrains Mono, monospace", fontWeight: 700, color: scoreColor, fontSize: 14 }}>
                {scoreLabel}
            </span>
            <span className="conf-hint">Signal valid until next 4H candle</span>
        </div>
    );
}
