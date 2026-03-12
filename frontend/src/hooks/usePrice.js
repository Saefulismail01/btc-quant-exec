import { useState, useEffect } from "react";

const WS_URL = "wss://fstream.binance.com/ws/btcusdt@aggTrade";

export function usePrice() {
    const [price, setPrice] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let ws;
        let reconnectTimeout;

        function connect() {
            ws = new WebSocket(WS_URL);

            ws.onopen = () => {
                setLoading(false);
            };

            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    // aggTrade stream: 'p' = price of the trade
                    if (data.p) {
                        setPrice(parseFloat(data.p));
                    }
                } catch (err) {
                    console.error("WS parse error:", err);
                }
            };

            ws.onerror = () => {
                setLoading(true);
            };

            ws.onclose = () => {
                // Auto-reconnect after 2 seconds on disconnect
                reconnectTimeout = setTimeout(connect, 2000);
            };
        }

        connect();

        return () => {
            clearTimeout(reconnectTimeout);
            if (ws) ws.close();
        };
    }, []);

    return { price, loading };
}
