function SnapRow({ label, value, prev }) {
    return (
        <div className="snap-row">
            <span className="snap-label">{label}</span>
            <span className="snap-value">{value}</span>
            {prev && <span className="snap-prev">{prev}</span>}
        </div>
    );
}

export default function MarketSnapshot({ price, metrics }) {
    const fmt = (v) => `$${v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    const obi = metrics?.order_book_imbalance ?? 0;
    const obiNote = obi > 0.2 ? "Buy Dominant" : obi < -0.2 ? "Sell Dominant" : "Balanced";

    return (
        <div className="card">
            <div className="section-title">Market Snapshot</div>
            <SnapRow label="BTC Price" value={fmt(price.now)} prev="—" />
            <SnapRow label="EMA 20" value={fmt(price.ema20)} prev={fmt(price.ema20_prev)} />
            <SnapRow label="EMA 50" value={fmt(price.ema50)} prev={fmt(price.ema50_prev)} />
            <SnapRow label="ATR 14" value={fmt(price.atr14)} prev="—" />
            <SnapRow label="Funding Rate" value={(metrics?.funding_rate ?? 0).toFixed(8)} prev="—" />
            <SnapRow label="Open Interest" value={`${(metrics?.open_interest ?? 0).toLocaleString()} BTC`} prev="—" />
            <SnapRow label="Order Book Imbalance" value={`${(obi).toFixed(4)}`} prev={obiNote} />
        </div>
    );
}
