import { useState, useEffect, useCallback } from "react";
import { fetchTradingStatus, fetchTradingHistory, resetTradingAccount } from "../api/btc-quant";

export function usePaperTrade(intervalMs = 10000) {
    const [status, setStatus] = useState(null);
    const [history, setHistory] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [resetting, setResetting] = useState(false);

    const load = useCallback(async () => {
        try {
            const [s, h] = await Promise.all([
                fetchTradingStatus(),
                fetchTradingHistory(),
            ]);
            setStatus(s);
            setHistory(h);
            setError(null);
        } catch (err) {
            setError("Failed to fetch paper trade data.");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        load();
        const id = setInterval(load, intervalMs);
        return () => clearInterval(id);
    }, [load, intervalMs]);

    const reset = useCallback(async () => {
        if (!window.confirm("Reset paper trading account to $10,000? All history will be lost.")) return;
        setResetting(true);
        try {
            await resetTradingAccount();
            await load();
        } catch (err) {
            setError("Reset failed.");
        } finally {
            setResetting(false);
        }
    }, [load]);

    // Derive equity curve from closed trades
    const equityCurve = (() => {
        const closed = [...history]
            .filter(t => t.status === "CLOSED")
            .sort((a, b) => a.timestamp - b.timestamp);

        let balance = 10000;
        return closed.map((t, i) => {
            balance += (t.pnl || 0);
            return {
                trade: i + 1,
                balance: parseFloat(balance.toFixed(2)),
                pnl: parseFloat((t.pnl || 0).toFixed(2)),
                date: new Date(t.timestamp).toLocaleDateString("en-GB", { month: "short", day: "numeric" }),
            };
        });
    })();

    // Summary stats
    const stats = (() => {
        const closed = history.filter(t => t.status === "CLOSED");
        const wins = closed.filter(t => (t.pnl || 0) > 0).length;
        const totalPnl = closed.reduce((sum, t) => sum + (t.pnl || 0), 0);
        const winRate = closed.length > 0 ? (wins / closed.length) * 100 : 0;
        const initialBalance = 10000;
        const currentBalance = status?.account?.balance ?? initialBalance;
        const totalPnlPct = ((currentBalance - initialBalance) / initialBalance) * 100;

        return {
            totalTrades: closed.length,
            wins,
            losses: closed.length - wins,
            winRate: winRate.toFixed(1),
            totalPnl: totalPnl.toFixed(2),
            totalPnlPct: totalPnlPct.toFixed(2),
            currentBalance: currentBalance.toFixed(2),
        };
    })();

    return { status, history, equityCurve, stats, loading, error, resetting, refresh: load, reset };
}
