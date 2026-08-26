import { useCallback, useEffect, useState } from "react";
import Sidebar from "./components/Sidebar";
import type { Page } from "./components/Sidebar";
import Topbar from "./components/Topbar";
import LoginGate from "./components/LoginGate";
import DashboardPage from "./pages/DashboardPage";
import EndpointsPage from "./pages/EndpointsPage";
import AlertsPage from "./pages/AlertsPage";
import IncidentesPage from "./pages/IncidentesPage";
import HoneyfilesPage from "./pages/HoneyfilesPage";
import RulesPage from "./pages/RulesPage";
import RespuestaPage from "./pages/RespuestaPage";
import ReportsPage from "./pages/ReportsPage";
import AdministracionPage from "./pages/AdministracionPage";
import PerfilPage from "./pages/PerfilPage";
import GlobalAlertsLayer from "./components/GlobalAlertsLayer";
import { GlobalAlertsProvider } from "./context/GlobalAlertsContext";
import { ApiError, fetchDashboardOverview, fetchMe } from "./api/client";
import type { DashboardOverview } from "./types/dashboard";
import type { ItemKind } from "./types/incidentes";

const POLL_INTERVAL_MS = 20_000;
const THEME_KEY = "alfa_sentinel_theme";

type Theme = "dark" | "light";

const PAGE_META: Record<Page, { title: string; subtitle: string }> = {
  dashboard: { title: "Panel de control", subtitle: "Resumen general de seguridad y estado de los endpoints" },
  endpoints: { title: "Endpoints", subtitle: "Equipos protegidos y estado de sus agentes" },
  alerts: { title: "Alertas", subtitle: "Detecciones generadas por las reglas heurísticas" },
  incidentes: { title: "Incidentes", subtitle: "Centro de investigación y respuesta" },
  honeyfiles: { title: "Honeyfiles", subtitle: "Archivos señuelo desplegados y su estado" },
  reglas: { title: "Reglas heurísticas", subtitle: "Qué detecta el sistema y con qué peso" },
  respuesta: { title: "Acciones de respuesta", subtitle: "Contención de endpoints ante una amenaza" },
  reportes: { title: "Reportes", subtitle: "Informes de seguridad, endpoints e incidentes" },
  administracion: { title: "Administración", subtitle: "Usuarios, agentes, configuración y auditoría" },
  perfil: { title: "Mi perfil", subtitle: "Información de tu cuenta en el Sistema ALFA-Sentinel" },
};

export function roleLabelFrom(roles: string[]): string {
  if (roles.length === 0) return "Usuario";
  return roles.map((r) => r.charAt(0).toUpperCase() + r.slice(1)).join(", ");
}

const getInitialPage = (): Page => {
  const path = window.location.pathname;
  if (path.startsWith("/endpoints")) return "endpoints";
  if (path.startsWith("/alertas") || path.startsWith("/alerts")) return "alerts";
  if (path.startsWith("/incidentes")) return "incidentes";
  if (path.startsWith("/honeyfiles")) return "honeyfiles";
  if (path.startsWith("/reglas")) return "reglas";
  if (path.startsWith("/respuesta")) return "respuesta";
  if (path.startsWith("/reportes")) return "reportes";
  if (path.startsWith("/administracion")) return "administracion";
  if (path.startsWith("/perfil")) return "perfil";
  return "dashboard";
};

const getInitialAlertsSelection = () => {
  const match = window.location.pathname.match(/\/(?:alertas|alerts)\/(\d+)/);
  if (match) return { id: parseInt(match[1], 10) };
  return null;
};

const getInitialIncidentesSelection = () => {
  const match = window.location.pathname.match(/\/incidentes\/(\d+)/);
  if (match) return { kind: "incident" as ItemKind, id: parseInt(match[1], 10) };
  return null;
};

export default function App() {
  const [page, setPage] = useState<Page>(getInitialPage);
  const [data, setData] = useState<DashboardOverview | null>(null);
  const [userName, setUserName] = useState("Usuario");
  const [roleLabel, setRoleLabel] = useState("Usuario");
  const [isAdmin, setIsAdmin] = useState(false);
  const [needsLogin, setNeedsLogin] = useState(false);
  const [alertsInitialSelection, setAlertsInitialSelection] = useState<{ id: number } | null>(getInitialAlertsSelection);
  const [incidentesInitialSelection, setIncidentesInitialSelection] = useState<{ kind: ItemKind; id: number } | null>(getInitialIncidentesSelection);
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

    fetchMe()
      .then((me) => {
        setUserName(me.full_name || me.username);
        setRoleLabel(roleLabelFrom(me.roles));
        setIsAdmin(me.roles.includes("admin"));
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [load]);

  useEffect(() => {
    let newUrl = "/";
    if (page !== "dashboard") {
      newUrl = `/${page}`;
      if (page === "incidentes" && incidentesInitialSelection?.kind === "incident") {
        newUrl = `/incidentes/${incidentesInitialSelection.id}`;
      } else if (page === "alerts" && alertsInitialSelection) {
        newUrl = `/alertas/${alertsInitialSelection.id}`;
      }
    }
    if (window.location.pathname !== newUrl && !window.location.pathname.endsWith(".html")) {
      window.history.pushState(null, "", newUrl);
    }
  }, [page, incidentesInitialSelection, alertsInitialSelection]);

  useEffect(() => {
    const onPopState = () => {
      setPage(getInitialPage());
      setAlertsInitialSelection(getInitialAlertsSelection());
      setIncidentesInitialSelection(getInitialIncidentesSelection());
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  function navigateTo(next: Page) {
    setAlertsInitialSelection(null);
    setIncidentesInitialSelection(null);
    setPage(next);
  }

  function openAlert(id: number) {
    setAlertsInitialSelection({ id });
    setPage("alerts");
  }

  function openIncident(id: number) {
    setIncidentesInitialSelection({ kind: "incident", id });
    setPage("incidentes");
  }

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
        Cargando Sistema ALFA-Sentinel...
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
    <GlobalAlertsProvider>
      <div id="app-shell" data-theme={theme} className="flex min-h-screen font-[Inter,system-ui,sans-serif] text-sm" style={wrapperStyle}>
        <div data-theme="dark" className="contents">
          <Sidebar
            page={page}
            onNavigate={navigateTo}
            alertsActive={data.summary.alerts_active}
            incidentsActive={data.summary.incidents_active}
          />
        </div>

        <div className="flex-1 min-w-0 flex flex-col relative overflow-x-hidden">
          <Topbar
            page={page}
            title={meta.title}
            subtitle={meta.subtitle}
            systemOk={data.system_status.db_ok && data.system_status.api_ok}
            userName={userName}
            roleLabel={roleLabel}
            theme={theme}
            onToggleTheme={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
            onLoggedOut={() => setNeedsLogin(true)}
            onSelectAlert={openAlert}
            onViewAllAlerts={() => navigateTo("alerts")}
            onOpenProfile={() => navigateTo("perfil")}
          />

          {page === "dashboard" ? (
            <DashboardPage data={data} />
          ) : page === "endpoints" ? (
            <EndpointsPage />
          ) : page === "alerts" ? (
            <AlertsPage initialAlertSelection={alertsInitialSelection} onViewIncident={openIncident} />
          ) : page === "incidentes" ? (
            <IncidentesPage initialSelection={incidentesInitialSelection} onViewAlert={openAlert} />
          ) : page === "honeyfiles" ? (
            <HoneyfilesPage />
          ) : page === "reglas" ? (
            <RulesPage />
          ) : page === "respuesta" ? (
            <RespuestaPage />
          ) : page === "reportes" ? (
            <ReportsPage />
          ) : page === "administracion" ? (
            <AdministracionPage isAdmin={isAdmin} />
          ) : (
            <PerfilPage roleLabel={roleLabel} />
          )}
        </div>

        <GlobalAlertsLayer onViewAlert={openAlert} onViewIncident={openIncident} />
      </div>
    </GlobalAlertsProvider>
  );
}
