import NotificationsBell from "./NotificationsBell";
import UserMenu from "./UserMenu";
import { ModuleMark } from "./Sidebar";
import type { Page } from "./Sidebar";
import { useGlobalAlertsContext } from "../context/GlobalAlertsContext";

interface TopbarProps {
  page: Page;
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
  page,
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
      <div className="min-w-0 flex-1 py-3 flex items-center gap-3.5">
        <div
          className="w-10 h-10 rounded-[11px] border grid place-items-center shrink-0"
          style={{
            background: "linear-gradient(145deg, var(--brand-soft), var(--brand-fill))",
            borderColor: "color-mix(in srgb, var(--brand) 20%, var(--line-soft))",
            color: "var(--brand)",
            boxShadow: "0 8px 22px rgba(37,99,235,.06)",
          }}
        >
          <ModuleMark page={page} size={19} />
        </div>

        <div className="min-w-0">
          <div className="text-[8.5px] font-bold tracking-[.16em] uppercase mb-0.5" style={{ color: "var(--brand)" }}>
            Consola central de seguridad
          </div>
          <div className="flex items-baseline gap-3 min-w-0">
            <h1 className="text-[18px] font-bold m-0 tracking-[-.025em] truncate" style={{ color: "var(--tx)" }}>
              {title}
            </h1>
            <span className="hidden 2xl:block text-[10.5px] font-medium truncate" style={{ color: "var(--tx-mute)" }}>
              {subtitle}
            </span>
          </div>
        </div>
      </div>

      <div className="ml-auto flex items-center gap-2.5 shrink-0">
        {openAlertsCount > 0 && (
          <div
            className="hidden xl:flex items-center gap-2 px-3 py-2 rounded-lg text-[10.5px] font-semibold border"
            style={{ background: "var(--crit-fill)", color: "var(--crit)", borderColor: "var(--crit-soft)" }}
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
          <span className="w-2 h-2 rounded-full" style={{ background: systemOk ? "var(--ok)" : "var(--crit)" }} />
          {systemOk ? "Servicios operativos" : "Servicios con problemas"}
        </div>

        <button
          onClick={onToggleTheme}
          title={theme === "dark" ? "Usar tema claro" : "Usar tema oscuro"}
          aria-label={theme === "dark" ? "Usar tema claro" : "Usar tema oscuro"}
          className="w-9 h-9 rounded-[10px] border grid place-items-center cursor-pointer transition-premium btn-hover"
          style={{ borderColor: "var(--line)", background: "var(--surf2)", color: "var(--tx-dim)", boxShadow: "var(--shadow)" }}
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
