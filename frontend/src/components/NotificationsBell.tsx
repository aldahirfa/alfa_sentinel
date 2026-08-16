import { useRef, useState } from "react";
import { fetchOpenAlerts } from "../api/client";
import type { OpenAlert } from "../api/client";
import { SEVERITY_LABEL, severityPillStyle } from "../lib/severity";
import { useClickOutside } from "../hooks/useClickOutside";

interface Props {
  count: number;
  onSelectAlert: (id: number) => void;
  onViewAll: () => void;
}

export default function NotificationsBell({ count, onSelectAlert, onViewAll }: Props) {
  const [open, setOpen] = useState(false);
  const [alerts, setAlerts] = useState<OpenAlert[] | null>(null);
  const [loading, setLoading] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useClickOutside(ref, () => setOpen(false));

  function toggle() {
    const next = !open;
    setOpen(next);
    if (next) {
      setLoading(true);
      fetchOpenAlerts()
        .then((res) => setAlerts(res.alerts))
        .catch(() => setAlerts([]))
        .finally(() => setLoading(false));
    }
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={toggle}
        className="relative w-9 h-9 rounded-lg border grid place-items-center cursor-pointer transition-premium btn-hover shadow-sm"
        style={{ borderColor: "var(--line)", background: "var(--surf2)", color: "var(--tx-dim)" }}
      >
        <i className="ph-fill ph-bell" style={{ fontSize: "17px" }} />
        {count > 0 && (
          <span
            className="absolute top-[5px] right-1.5 w-1.5 h-1.5 rounded-full"
            style={{ background: "var(--crit)" }}
          />
        )}
      </button>

      {open && (
        <div
          className="absolute right-0 top-[48px] w-[340px] rounded-xl border z-30 overflow-hidden"
          style={{ background: "var(--surf)", borderColor: "var(--line-soft)", boxShadow: "var(--shadow-lg)" }}
        >
          <div className="px-3.5 py-3 border-b flex items-center" style={{ borderColor: "var(--line-soft)" }}>
            <span className="text-[13px] font-semibold" style={{ color: "var(--tx)" }}>
              Alertas nuevas
            </span>
            {count > 0 && (
              <span
                className="ml-auto text-[10.5px] font-semibold px-1.5 py-px rounded-full"
                style={{ background: "var(--crit-soft)", color: "var(--crit)" }}
              >
                {count}
              </span>
            )}
          </div>

          <div className="max-h-[320px] overflow-y-auto">
            {loading ? (
              <div className="px-3.5 py-6 text-center text-xs" style={{ color: "var(--tx-mute)" }}>
                Cargando...
              </div>
            ) : !alerts || alerts.length === 0 ? (
              <div className="px-3.5 py-6 text-center text-xs" style={{ color: "var(--tx-mute)" }}>
                No hay alertas nuevas.
              </div>
            ) : (
              alerts.map((a) => (
                <button
                  key={a.id}
                  onClick={() => {
                    setOpen(false);
                    onSelectAlert(a.id);
                  }}
                  className="flex flex-col gap-1.5 px-4 py-3 border-b w-full text-left bg-transparent cursor-pointer transition-colors hover:bg-[var(--surf2)]"
                  style={{ borderColor: "var(--line-soft)" }}
                >
                  <div className="flex items-center gap-2">
                    <span
                      className="text-[9.5px] font-bold tracking-wide px-1.5 py-0.5 rounded"
                      style={severityPillStyle(a.severity)}
                    >
                      {SEVERITY_LABEL[a.severity].toUpperCase()}
                    </span>
                    <span className="text-[12px] font-medium" style={{ color: "var(--tx)" }}>{a.hostname}</span>
                    <span className="ml-auto text-[10.5px]" style={{ color: "var(--tx-mute)" }}>{a.created_at}</span>
                  </div>
                  <div className="text-[11.5px]" style={{ color: "var(--tx-dim)" }}>{a.title}</div>
                </button>
              ))
            )}
          </div>

          <button
            onClick={() => {
              setOpen(false);
              onViewAll();
            }}
            className="block w-full text-center text-[12.5px] font-bold bg-transparent border-0 cursor-pointer px-4 py-3 transition-colors hover:bg-[var(--brand-soft)]"
            style={{ color: "var(--brand)" }}
          >
            Ver todas las alertas
          </button>
        </div>
      )}
    </div>
  );
}
