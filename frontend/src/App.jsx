import { useState, useEffect } from "react";
import "./styles/index.css";
import Dashboard from "./pages/Dashboard";
import PaperTrade from "./pages/PaperTrade";

export default function App() {
    const [path, setPath] = useState(window.location.pathname);

    useEffect(() => {
        const onPopState = () => setPath(window.location.pathname);
        window.addEventListener("popstate", onPopState);
        return () => window.removeEventListener("popstate", onPopState);
    }, []);

    // Handle internal navigation without reload
    const navigate = (href) => {
        window.history.pushState({}, "", href);
        setPath(href);
    };

    // Normalize path to handle things like /paper-trade/ 
    const normalizedPath = path.endsWith("/") && path.length > 1 ? path.slice(0, -1) : path;

    if (normalizedPath === "/paper-trade") {
        return <PaperTrade />;
    }

    return <Dashboard />;
}
