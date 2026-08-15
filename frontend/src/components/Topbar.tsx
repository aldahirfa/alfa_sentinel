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
}: TopbarProps) {
  return (
    <header
      className="sticky top-0 z-20 border-b px-[22px] py-3.5 flex items-center gap-5"
      style={{ background: "var(--surf)", borderColor: "var(--line)" }}
    >
      <div className="min-w-0">
        <h1 className="text-[19px] font-semibold m-0 tracking-tight" style={{ color: "var(--tx)" }}>
          {title}
        </h1>
        <div className="text-xs mt-0.5" style={{ color: "var(--tx-mute)" }}>
          {subtitle}
        </div>
      </div>

      <div className="ml-auto flex items-center gap-3">
        <div
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-full text-xs font-medium"
          style={{
            background: systemOk ? "var(--ok-soft)" : "var(--crit-soft)",
            color: systemOk ? "var(--ok)" : "var(--crit)",
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
          className="w-[34px] h-[34px] rounded-lg border grid place-items-center cursor-pointer transition-colors"
          style={{ borderColor: "var(--line)", background: "var(--surf2)", color: "var(--tx-dim)" }}
        >
          <i className={theme === "dark" ? "ph ph-sun" : "ph ph-moon"} style={{ fontSize: "16px" }} />
        </button>

        <NotificationsBell count={notificationCount} />

        <div className="w-px h-[26px]" style={{ background: "var(--line)" }} />

        <UserMenu userName={userName} roleLabel={roleLabel} onLoggedOut={onLoggedOut} />
      </div>
    </header>
  );
}
