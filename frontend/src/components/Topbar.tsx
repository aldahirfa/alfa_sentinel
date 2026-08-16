import NotificationsBell from "./NotificationsBell";
import UserMenu from "./UserMenu";

interface TopbarProps {
  title?: string;
  subtitle?: string;
  systemOk: boolean;
  notificationCount: number;
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
  notificationCount,
  userName,
  roleLabel,
  theme,
  onToggleTheme,
  onLoggedOut,
  onSelectAlert,
  onViewAllAlerts,
  onOpenProfile,
}: TopbarProps) {
  return (
    <header
      className="sticky top-0 z-20 border-b px-6 py-4 flex items-center gap-5 shadow-sm"
      style={{ background: "var(--surf)", borderColor: "var(--line-soft)" }}
    >
      <div className="min-w-0 flex-1">
        <h1 className="text-xl font-bold m-0 tracking-tight" style={{ color: "var(--tx)" }}>
          {title}
        </h1>
        <div className="text-[12.5px] mt-1 font-medium tracking-wide" style={{ color: "var(--tx-mute)" }}>
          {subtitle}
        </div>
      </div>

      <div className="ml-auto flex items-center gap-3">
        <div
          className="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-bold tracking-wide border"
          style={{
            background: systemOk ? "var(--ok-soft)" : "var(--crit-soft)",
            color: systemOk ? "var(--ok)" : "var(--crit)",
            borderColor: systemOk ? "var(--ok-soft)" : "var(--crit-soft)",
          }}
        >
          <span
            className="w-1.5 h-1.5 rounded-full"
            style={{
              background: systemOk ? "var(--ok)" : "var(--crit)",
              boxShadow: `0 0 0 3px ${systemOk ? "var(--ok-soft)" : "var(--crit-soft)"}`,
            }}
          />
          {systemOk ? "Sistema operativo" : "Sistema con problemas"}
        </div>

        <button
          onClick={onToggleTheme}
          title="Cambiar tema"
          className="w-9 h-9 rounded-lg border grid place-items-center cursor-pointer transition-premium btn-hover shadow-sm"
          style={{ borderColor: "var(--line)", background: "var(--surf2)", color: "var(--tx-dim)" }}
        >
          <i className={theme === "dark" ? "ph-fill ph-sun" : "ph-fill ph-moon"} style={{ fontSize: "17px" }} />
        </button>

        <NotificationsBell count={notificationCount} onSelectAlert={onSelectAlert} onViewAll={onViewAllAlerts} />

        <div className="w-px h-[26px]" style={{ background: "var(--line)" }} />

        <UserMenu userName={userName} roleLabel={roleLabel} onLoggedOut={onLoggedOut} onOpenProfile={onOpenProfile} />
      </div>
    </header>
  );
}
