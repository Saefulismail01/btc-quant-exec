import { useState, useEffect, useCallback } from "react";
import { fetchSignal } from "../api/btc-quant";

export function useSignal(intervalMs = 60000) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [lastUpdated, setLastUpdated] = useState(null);

    const load = useCallback(async () => {
        try {
            setLoading(true);
            setError(null);
            const res = await fetchSignal();
            setData(res);
            setLastUpdated(new Date());
        } catch (e) {
            setError(e.response?.data?.detail || e.message);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        load();
        const id = setInterval(load, intervalMs);
        return () => clearInterval(id);
    }, [load, intervalMs]);

    return { data, loading, error, lastUpdated, refresh: load };
}
