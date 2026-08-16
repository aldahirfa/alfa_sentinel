import { useRef, useState } from "react";
import { logout } from "../api/client";
import { useClickOutside } from "../hooks/useClickOutside";

interface Props {
  userName: string;
  roleLabel: string;
  onLoggedOut: () => void;
  onOpenProfile: () => void;
}

export default function UserMenu({ userName, roleLabel, onLoggedOut, onOpenProfile }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useClickOutside(ref, () => setOpen(false));

  const initials = userName
    .split(/\s+/)
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  async function handleLogout() {
    setOpen(false);
    await logout();
    onLoggedOut();
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2.5 cursor-pointer bg-transparent border-0"
      >
        <div
          className="w-[30px] h-[30px] rounded-full border grid place-items-center text-[11px] font-semibold"
          style={{ background: "var(--brand-soft)", borderColor: "var(--brand)", color: "var(--brand)" }}
        >
          {initials || "?"}
        </div>
        <div className="leading-tight hidden sm:block text-left">
          <div className="text-[12.5px] font-medium" style={{ color: "var(--tx)" }}>{userName}</div>
          <div className="text-[10.5px]" style={{ color: "var(--tx-mute)" }}>{roleLabel}</div>
        </div>
        <i className="ph ph-caret-down text-xs" style={{ color: "var(--tx-mute)" }} />
      </button>

      {open && (
        <div
          className="absolute right-0 top-[48px] w-[220px] rounded-xl border z-30 overflow-hidden"
          style={{ background: "var(--surf)", borderColor: "var(--line-soft)", boxShadow: "var(--shadow-lg)" }}
        >
          <div className="px-3.5 py-3 border-b" style={{ borderColor: "var(--line-soft)" }}>
            <div className="text-[12.5px] font-semibold" style={{ color: "var(--tx)" }}>{userName}</div>
            <div className="text-[11px] mt-0.5" style={{ color: "var(--tx-mute)" }}>{roleLabel}</div>
          </div>
          <button
            onClick={() => {
              setOpen(false);
              onOpenProfile();
            }}
            className="flex items-center gap-2.5 px-4 py-3 text-[13px] font-medium w-full text-left bg-transparent border-0 cursor-pointer transition-colors hover:bg-[var(--surf2)]"
            style={{ color: "var(--tx-dim)" }}
          >
            <i className="ph ph-user-circle" style={{ fontSize: "15px" }} />
            Mi perfil
          </button>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2.5 px-4 py-3 text-[13px] font-medium w-full text-left bg-transparent border-0 cursor-pointer border-t transition-colors hover:bg-[var(--crit-soft)]"
            style={{ color: "var(--crit)", borderColor: "var(--line-soft)" }}
          >
            <i className="ph ph-sign-out" style={{ fontSize: "15px" }} />
            Cerrar sesión
          </button>
        </div>
      )}
    </div>
  );
}
