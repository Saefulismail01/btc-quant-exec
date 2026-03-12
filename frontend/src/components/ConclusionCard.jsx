const PROB_CONFIG = {
    high: { cls: "callout-high", emoji: "🟢", label: "High Probability Setup" },
    med:  { cls: "callout-med",  emoji: "🟡", label: "Medium Probability Setup" },
    low:  { cls: "callout-low",  emoji: "🔴", label: "Low Probability Setup" },
};

export default function ConclusionCard({ confluence, validityUtc }) {
    const cfg = PROB_CONFIG[confluence.probability] ?? PROB_CONFIG.low;

    return (
        <div className="card">
            <div className="section-title">Signal Conclusion</div>

            <div className={cfg.cls}>
                {/* Header row: probability + verdict + score */}
                <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                    <strong>{cfg.emoji} {cfg.label}</strong>
                    <span style={{
                        fontFamily: "JetBrains Mono, monospace",
                        fontSize: 11,
                        fontWeight: 700,
                        padding: "1px 7px",
                        borderRadius: 4,
                        background: "rgba(0,0,0,0.08)",
                    }}>
                        {confluence.verdict ?? "NEUTRAL"}
                    </span>
                    <span style={{
                        fontFamily: "JetBrains Mono, monospace",
                        fontSize: 11,
                        opacity: 0.75,
                    }}>
                        {confluence.confluence_score ?? 0}/100
                    </span>
                </div>

                {/* Conclusion summary */}
                <div style={{ marginTop: 6, fontSize: 12, lineHeight: 1.5 }}>
                    {confluence.conclusion}
                </div>

                {/* LLM rationale */}
                {confluence.rationale && (
                    <div style={{
                        marginTop: 8,
                        paddingTop: 8,
                        borderTop: "1px solid rgba(0,0,0,0.08)",
                        fontSize: 11.5,
                        lineHeight: 1.6,
                        whiteSpace: "pre-line",
                        opacity: 0.85,
                    }}>
                        {confluence.rationale}
                    </div>
                )}
            </div>

            <div style={{ marginTop: 10, fontSize: 11, color: "#6b7280" }}>
                ⏱ Valid until:{" "}
                <strong>{validityUtc?.replace("T", " ").replace("Z", " UTC")}</strong>
                <br />Auto-refresh every 60 seconds
            </div>
        </div>
    );
}
