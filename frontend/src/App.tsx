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
  reportes: { title: "Reports", subtitle: "Informes de seguridad, endpoints e incidentes" },
  administracion: { title: "Administración", subtitle: "Usuarios, agentes, configuración y auditoría" },
  perfil: { title: "Mi perfil", subtitle: "Información de tu cuenta en ALFA_SENTINEL" },
};

// No hay tabla de roles->etiqueta en el servidor (ver server/templates/
// usuarios.html: "Hoy solo existe el rol admin"). Se capitaliza el
// valor real tal cual viene de la sesión, sin inventar una etiqueta.
// Exportada porque PerfilPage necesita el mismo texto que ya se
// muestra en el topbar/menú de usuario -- una sola fuente de verdad.
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
  // Selección de alerta pedida desde la campana de notificaciones --
  // se envuelve en un objeto nuevo en cada click para que AlertsPage
  // pueda reabrir el drawer aunque sea la misma alerta dos veces
  // seguidas (ver AlertsPage.tsx::initialAlertSelection).
  const [alertsInitialSelection, setAlertsInitialSelection] = useState<{ id: number } | null>(getInitialAlertsSelection);
  // Mismo patrón que arriba, pero para navegar a Incidentes y abrir un
  // incidente puntual -- usado desde "Ver incidente" en AlertDrawer.
  const [incidentesInitialSelection, setIncidentesInitialSelection] =
    useState<{ kind: ItemKind; id: number } | null>(getInitialIncidentesSelection);
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

  // Navegación "plana" (sidebar, "Mi perfil", "Ver todas las
  // alertas") -- SIEMPRE limpia cualquier selección pendiente de una
  // notificación anterior. Sin esto, entrar a Alertas/Incidentes por
  // el sidebar después de haber llegado alguna vez desde una
  // notificación reabría el mismo drawer de esa vez, porque
  // alertsInitialSelection/incidentesInitialSelection quedaban en
  // memoria entre navegaciones (viven acá, en App.tsx, no en la
  // página que se desmonta). Este es el único lugar que debe "abrir
  // sin querer" un drawer -- todo lo demás pasa por acá.
  function navigateTo(next: Page) {
    setAlertsInitialSelection(null);
    setIncidentesInitialSelection(null);
    setPage(next);
  }

  // Navegación interna compartida entre pantallas -- reemplaza los
  // <a href="/incidentes/...">/<a href="/detecciones/...."> que
  // antes mandaban a Jinja2. "Ver incidente" desde una alerta y
  // "Ver alerta original" desde un incidente usan esto mismo. A
  // diferencia de navigateTo(), estas SÍ dejan una selección pendiente
  // a propósito -- son la excepción válida: hay una intención
  // explícita de ver un registro concreto (ver también
  // Topbar::onSelectAlert, misma función).
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
    <div id="app-shell" data-theme={theme} className="flex min-h-screen font-[Inter,system-ui,sans-serif] text-sm" style={wrapperStyle}>
      {/* id="app-shell": los modales que usan un portal (ej.
          RuleEditModal.tsx) lo apuntan acá en vez de a document.body --
          las variables CSS del tema (--surf, --tx, etc.) se definen en
          este div vía [data-theme], no en <html>/<body>, así que un
          portal directo a document.body queda fuera de su alcance y
          los colores salen transparentes/sin definir. */}
      {/* La barra lateral se mantiene siempre oscura, incluso en tema
          claro (pedido explícito) -- data-theme anidado resuelve las
          variables CSS del sidebar al set oscuro sin tocar el resto
          de la app. display:contents para que no agregue una caja
          extra al layout flex de afuera. */}
      <div data-theme="dark" className="contents">
        <Sidebar
          page={page}
          onNavigate={navigateTo}
          alertsActive={data.summary.alerts_active}
          incidentsActive={data.summary.incidents_active}
        />
      </div>

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
    </div>
  );
}
