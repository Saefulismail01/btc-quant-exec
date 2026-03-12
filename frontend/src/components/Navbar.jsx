const NAV_LINKS = [
    { href: "/", label: "📊 Dashboard" },
    { href: "/paper-trade", label: "📋 Paper Trade" },
];

export default function Navbar({ lastUpdated, onRefresh, loading, extraContent }) {
    const ts = lastUpdated
        ? lastUpdated.toUTCString().replace("GMT", "UTC")
        : "—";

    const currentPath = window.location.pathname;

    return (
        <header className="navbar">
            <div className="navbar-left">
                <span className="navbar-logo">⚡</span>
                <div>
                    <div className="navbar-title">BTC-QUANT</div>
                    <div className="navbar-subtitle">
                        Quantitative Scalping · Signal Intelligence · BTC/USDT Perpetual
                    </div>
                </div>
                <nav style={{ display: "flex", gap: 4, marginLeft: 16 }}>
                    {NAV_LINKS.map(({ href, label }) => (
                        <a
                            key={href}
                            href={href}
                            onClick={(e) => {
                                e.preventDefault();
                                window.history.pushState({}, "", href);
                                window.dispatchEvent(new PopStateEvent("popstate"));
                            }}
                            style={{
                                padding: "4px 12px",
                                borderRadius: 6,
                                fontSize: 12,
                                fontWeight: 600,
                                textDecoration: "none",
                                background: currentPath === href ? "#f3f4f6" : "transparent",
                                color: currentPath === href ? "#1a1d23" : "#6b7280",
                                border: currentPath === href ? "1px solid #e5e7eb" : "1px solid transparent",
                            }}
                        >
                            {label}
                        </a>
                    ))}
                </nav>
            </div>

            <div className="navbar-right">
                <span className="live-pill">
                    <span className="live-dot" />
                    LIVE
                </span>
                {ts !== "—" && <span className="navbar-ts">{ts}</span>}
                {extraContent}
                <button
                    className="btn-refresh"
                    onClick={onRefresh}
                    disabled={loading}
                >
                    {loading ? "Loading…" : "↻ Refresh"}
                </button>
            </div>
        </header>
    );
}
