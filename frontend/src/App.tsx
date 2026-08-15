import { useCallback, useEffect, useState } from "react";
import Sidebar from "./components/Sidebar";
import type { Page } from "./components/Sidebar";
import Topbar from "./components/Topbar";
import LoginGate from "./components/LoginGate";
import DashboardPage from "./pages/DashboardPage";
import EndpointsPage from "./pages/EndpointsPage";
import { ApiError, fetchDashboardOverview, fetchMe } from "./api/client";
import type { DashboardOverview } from "./types/dashboard";

const POLL_INTERVAL_MS = 20_000;
const THEME_KEY = "alfa_sentinel_theme";

type Theme = "dark" | "light";

const PAGE_META: Record<Page, { title: string; subtitle: string }> = {
  dashboard: { title: "Panel de control", subtitle: "Resumen general de seguridad y estado de los endpoints" },
  endpoints: { title: "Endpoints", subtitle: "Equipos protegidos y estado de sus agentes" },
};

// No hay tabla de roles->etiqueta en el servidor (ver server/templates/
// usuarios.html: "Hoy solo existe el rol admin"). Se capitaliza el
// valor real tal cual viene de la sesión, sin inventar una etiqueta.
function roleLabelFrom(roles: string[]): string {
  if (roles.length === 0) return "Usuario";
  return roles.map((r) => r.charAt(0).toUpperCase() + r.slice(1)).join(", ");
}

export default function App() {
  const [page, setPage] = useState<Page>("dashboard");
  const [data, setData] = useState<DashboardOverview | null>(null);
  const [userName, setUserName] = useState("Usuario");
  const [roleLabel, setRoleLabel] = useState("Usuario");
  const [needsLogin, setNeedsLogin] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = localStorage.getItem(THEME_KEY);
    return saved === "light" ? "light" : "dark";
  });

  useEffect(() => {
    localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  const load = useCallback(() => {
    fetchDashboardOverview()
      .then((res) => {
        setData(res);
        setLoadError(null);
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          setNeedsLogin(true);
        } else {
          setLoadError("No se pudo cargar el panel de control.");
        }
      });

    // Nombre y rol real de la sesión (GET /me) -- si falla (p.ej.
    // sesión recién vencida), se mantienen los textos genéricos
    // anteriores en vez de romper el panel.
    fetchMe()
      .then((me) => {
        setUserName(me.full_name || me.username);
        setRoleLabel(roleLabelFrom(me.roles));
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [load]);

  const wrapperStyle = { background: "var(--bg)", color: "var(--tx)" };

  if (needsLogin) {
    return (
      <LoginGate
        onSuccess={() => {
          setNeedsLogin(false);
          load();
        }}
      />
    );
  }

  if (loadError) {
    return (
      <div data-theme={theme} className="min-h-screen flex items-center justify-center text-sm" style={wrapperStyle}>
        {loadError}
      </div>
    );
  }

  if (!data) {
    return (
      <div data-theme={theme} className="min-h-screen flex items-center justify-center text-sm" style={{ ...wrapperStyle, color: "var(--tx-mute)" }}>
        Cargando ALFA_SENTINEL...
      </div>
    );
  }

  if (!data.db_ok) {
    return (
      <div data-theme={theme} className="min-h-screen flex items-center justify-center text-sm" style={{ ...wrapperStyle, color: "var(--crit)" }}>
        No se pudo conectar con la base de datos. Reintentando...
      </div>
    );
  }

  const meta = PAGE_META[page];

  return (
    <div data-theme={theme} className="flex min-h-screen font-[Inter,system-ui,sans-serif] text-sm" style={wrapperStyle}>
      <Sidebar
        page={page}
        onNavigate={setPage}
        alertsActive={data.summary.alerts_active}
        incidentsActive={data.summary.incidents_active}
      />

      <div className="flex-1 min-w-0 flex flex-col">
        <Topbar
          title={meta.title}
          subtitle={meta.subtitle}
          systemOk={data.system_status.db_ok && data.system_status.api_ok}
          notificationCount={data.summary.alerts_active}
          userName={userName}
          roleLabel={roleLabel}
          theme={theme}
          onToggleTheme={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
          onLoggedOut={() => setNeedsLogin(true)}
        />

        {page === "dashboard" ? <DashboardPage data={data} /> : <EndpointsPage />}
      </div>
    </div>
  );
}
