import type { RecentActivityItem } from "../types/dashboard";
import { SEVERITY_VAR } from "../lib/severity";

interface Props {
  items: RecentActivityItem[];
}

function dotColor(item: RecentActivityItem): string {
  if (item.severity) return SEVERITY_VAR[item.severity];
  if (item.kind === "honeyfile_created") return "var(--ok)";
  return "var(--ok)"; // endpoint_registered
}

function titleColor(item: RecentActivityItem): string {
  if (item.severity === "CRÍTICO") return "var(--crit)";
  if (item.severity === "ALTO") return "var(--high)";
  return "var(--tx)";
}

export default function RecentActivityTimeline({ items }: Props) {
  return (
    <section
      className="rounded-xl border p-5 shadow-sm flex flex-col h-full"
      style={{ background: "var(--surf)", borderColor: "var(--line-soft)" }}
    >
      <h2 className="text-[14px] font-bold tracking-tight m-0" style={{ color: "var(--tx)" }}>Actividad reciente</h2>

      {items.length === 0 ? (
        <p className="text-[12.5px] py-6 text-center" style={{ color: "var(--tx-mute)" }}>
          Sin actividad todavía.
        </p>
      ) : (
        <div className="flex flex-col h-full gap-0 relative mt-auto before:absolute before:inset-y-2 before:left-[59px] before:w-px before:bg-[var(--line)]">
          {items.map((item, i) => (
            <div key={i} className="flex gap-4 relative py-2.5">
              <div className="w-[45px] shrink-0 text-right text-[11.5px] font-bold mt-0.5" style={{ color: "var(--tx-mute)" }}>
                {item.time}
              </div>
              <div className="w-[11px] h-[11px] rounded-full mt-1.5 z-10 shrink-0 ring-4 ring-[var(--surf)]" style={{ background: dotColor(item) }} />
              <div className="min-w-0 pb-1">
                <div className="text-[13px] font-bold tracking-tight" style={{ color: titleColor(item) }}>
                  {item.type_label}
                </div>
                <div className="text-[11.5px] mt-0.5 font-medium truncate" style={{ color: "var(--tx-mute)" }}>
                  {item.hostname} · {item.label}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
