import NotificationsBell from "./NotificationsBell";
import UserMenu from "./UserMenu";
import { useGlobalAlertsContext } from "../context/GlobalAlertsContext";

interface TopbarProps {
  title?: string;
  subtitle?: string;
  systemOk: boolean;
  userName: string;
  roleLabel: string;
  theme: "dark" | "light";
  onToggleTheme: () => void;
  onLoggedOut: () => void;
  onSelectAlert: (id: number) => void;
  onViewAllAlerts: () => void;
  onOpenProfile: () => void;
}

export default function Topbar({
  title = "Panel de control",
  subtitle = "Resumen general de seguridad y estado de los endpoints",
  systemOk,
  userName,
  roleLabel,
  theme,
  onToggleTheme,
  onLoggedOut,
  onSelectAlert,
  onViewAllAlerts,
  onOpenProfile,
}: TopbarProps) {
  const { openAlertsCount } = useGlobalAlertsContext();

  return (
    <header
      className="sticky top-0 z-20 min-h-[76px] border-b px-6 flex items-center gap-5 glass-panel"
      style={{
        borderColor: "var(--line-soft)",
        boxShadow: "0 1px 0 rgba(255,255,255,.015), 0 12px 38px rgba(0,0,0,.055)",
      }}
    >
      <div className="min-w-0 flex-1 py-3.5">
        <div className="flex items-center gap-2.5 mb-1">
          <span
            className="text-[9px] font-bold tracking-[.16em] uppercase"
            style={{ color: "var(--brand)" }}
          >
            Consola central
          </span>
          <span className="w-1 h-1 rounded-full" style={{ background: "var(--line)" }} />
          <span className="text-[9px] font-semibold tracking-[.12em] uppercase" style={{ color: "var(--tx-mute)" }}>
            Blue Team
          </span>
        </div>
        <div className="flex items-baseline gap-3 min-w-0">
          <h1 className="text-[19px] font-bold m-0 tracking-[-.025em] truncate" style={{ color: "var(--tx)" }}>
            {title}
          </h1>
          <span className="hidden 2xl:block text-[11.5px] font-medium truncate" style={{ color: "var(--tx-mute)" }}>
            {subtitle}
          </span>
        </div>
      </div>

      <div className="ml-auto flex items-center gap-2.5 shrink-0">
        {openAlertsCount > 0 && (
          <div
            className="hidden xl:flex items-center gap-2 px-3 py-2 rounded-lg text-[10.5px] font-semibold border"
            style={{
              background: "var(--crit-fill)",
              color: "var(--crit)",
              borderColor: "var(--crit-soft)",
            }}
          >
            <i className="ph-fill ph-warning-circle" style={{ fontSize: "14px" }} />
            {openAlertsCount} {openAlertsCount === 1 ? "alerta abierta" : "alertas abiertas"}
          </div>
        )}

        <div
          className="hidden lg:flex items-center gap-2 px-3 py-2 rounded-lg text-[10.5px] font-semibold border"
          style={{
            background: systemOk ? "var(--ok-soft)" : "var(--crit-soft)",
            color: systemOk ? "var(--ok)" : "var(--crit)",
            borderColor: systemOk ? "color-mix(in srgb, var(--ok) 22%, transparent)" : "var(--crit-soft)",
          }}
        >
          <span className="relative flex h-2 w-2">
            {systemOk && (
              <span
                className="absolute inline-flex h-full w-full rounded-full opacity-20"
                style={{ background: "var(--ok)", animation: "alfaSoftPulse 2.4s ease-in-out infinite" }}
              />
            )}
            <span className="relative inline-flex rounded-full h-2 w-2" style={{ background: systemOk ? "var(--ok)" : "var(--crit)" }} />
          </span>
          {systemOk ? "Servicios operativos" : "Servicios con problemas"}
        </div>

        <button
          onClick={onToggleTheme}
          title={theme === "dark" ? "Usar tema claro" : "Usar tema oscuro"}
          aria-label={theme === "dark" ? "Usar tema claro" : "Usar tema oscuro"}
          className="w-9 h-9 rounded-[10px] border grid place-items-center cursor-pointer transition-premium btn-hover"
          style={{
            borderColor: "var(--line)",
            background: "var(--surf2)",
            color: "var(--tx-dim)",
            boxShadow: "var(--shadow)",
          }}
        >
          <i className={theme === "dark" ? "ph-fill ph-sun" : "ph-fill ph-moon"} style={{ fontSize: "16px" }} />
        </button>

        <NotificationsBell count={openAlertsCount} onSelectAlert={onSelectAlert} onViewAll={onViewAllAlerts} />

        <div className="w-px h-[28px] mx-0.5" style={{ background: "var(--line-soft)" }} />

        <UserMenu userName={userName} roleLabel={roleLabel} onLoggedOut={onLoggedOut} onOpenProfile={onOpenProfile} />
      </div>
    </header>
  );
}
