export default function MetricCard({ label, value, delta, deltaType = "neutral" }) {
    return (
        <div className="metric-card">
            <div className="metric-label">{label}</div>
            <div className="metric-value">{value}</div>
            {delta && (
                <div className={`metric-delta delta-${deltaType}`}>{delta}</div>
            )}
        </div>
    );
}
