import axios from "axios";

const getApiUrl = () => {
    if (typeof window !== 'undefined') {
        // Automatically detect the current host (like 192.168.1.13) and use port 8000
        return `http://${window.location.hostname}:8000`;
    }
    return import.meta.env.VITE_API_URL || "http://localhost:8000";
};

const API = axios.create({
    baseURL: getApiUrl(),
    timeout: 15000,
});

export const fetchSignal = () => API.get("/api/signal").then(r => r.data);
export const fetchPrice = () => API.get("/api/price").then(r => r.data);
export const fetchMetrics = () => API.get("/api/metrics").then(r => r.data);
export const fetchHealth = () => API.get("/api/health").then(r => r.data);
export const fetchTradingStatus = () => API.get("/api/trading/status").then(r => r.data);
export const fetchTradingHistory = () => API.get("/api/trading/history").then(r => r.data);
export const resetTradingAccount = () => API.post("/api/trading/reset").then(r => r.data);
