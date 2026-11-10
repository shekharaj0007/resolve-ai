import { createContext, useContext, useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { api } from "../api";
import { AGENTS } from "../format";

const AgentContext = createContext({ agent: AGENTS[0], setAgent: () => {} });

export function useAgent() {
  return useContext(AgentContext);
}

function embedderLabel(name) {
  if (!name || name === "pending" || name === "unavailable") return "Embedder warming";
  if (name.includes("MiniLM")) return "MiniLM embeddings";
  if (name.includes("svd")) return "TF-IDF SVD embeddings";
  return name;
}

const LINKS = [
  { to: "/", label: "Overview", end: true },
  { to: "/inbox", label: "Inbox", match: ["/inbox", "/tickets"] },
  { to: "/search", label: "Semantic search" },
  { to: "/models", label: "Models" },
];

export default function Shell() {
  const location = useLocation();
  const [agent, setAgent] = useState(() => localStorage.getItem("resolveai.agent") || AGENTS[0]);
  const [health, setHealth] = useState(undefined);

  useEffect(() => {
    localStorage.setItem("resolveai.agent", agent);
  }, [agent]);

  useEffect(() => {
    let ignore = false;
    api.health().then((next) => {
      if (!ignore) setHealth(next);
    }).catch(() => {
      if (!ignore) setHealth(null);
    });
    return () => {
      ignore = true;
    };
  }, []);

  return (
    <AgentContext.Provider value={{ agent, setAgent }}>
      <div className="shell">
        <aside className="sidebar">
          <div className="brand">
            <span className="brand-mark" aria-hidden="true" />
            <div>
              <strong>ResolveAI</strong>
              <span>Fieldnote queue</span>
            </div>
          </div>
          <nav className="nav">
            {LINKS.map((link) => {
              const active = link.match
                ? link.match.some((prefix) => location.pathname === prefix || location.pathname.startsWith(`${prefix}/`))
                : undefined;
              return (
                <NavLink
                  key={link.to}
                  to={link.to}
                  end={link.end}
                  className={({ isActive }) => `nav-link${active ?? isActive ? " active" : ""}`}
                >
                  {link.label}
                </NavLink>
              );
            })}
          </nav>
          <div className="sidebar-foot">
            <label className="field">
              Agent on duty
              <select value={agent} onChange={(event) => setAgent(event.target.value)}>
                {AGENTS.map((name) => (
                  <option key={name}>{name}</option>
                ))}
              </select>
            </label>
            <div className="foot-meta">
              <div className="health-row">
                <span className="dot" style={{ background: health?.models_loaded ? "#7dcea0" : "#e2b657" }} />
                {health == null ? "API offline" : health.models_loaded ? "Models loaded" : "Models not trained"}
              </div>
              <div>{health?.database === "postgresql" ? "PostgreSQL" : health?.database === "sqlite" ? "SQLite" : "Database"}</div>
              <div>{embedderLabel(health?.embedder)}</div>
            </div>
          </div>
        </aside>
        <main className="main">
          {health === null && (
            <div className="banner">The API is not reachable. Start it with uvicorn on port 8000.</div>
          )}
          {health && !health.models_loaded && (
            <div className="banner">Models are not trained yet. From the repo root run python -m backend.scripts.bootstrap.</div>
          )}
          <Outlet />
        </main>
      </div>
    </AgentContext.Provider>
  );
}
