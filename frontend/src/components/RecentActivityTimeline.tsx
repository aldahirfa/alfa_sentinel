import type { RecentActivityItem } from "../types/dashboard";
import { SEVERITY_VAR } from "../lib/severity";

interface Props {
  items: RecentActivityItem[];
}

function dotColor(item: RecentActivityItem): string {
  if (item.severity) return SEVERITY_VAR[item.severity];
  if (item.kind === "honeyfile_created") return "var(--info)";
  return "var(--ok)";
}

function titleColor(item: RecentActivityItem): string {
  if (item.severity === "CRÍTICO") return "var(--crit)";
  if (item.severity === "ALTO") return "var(--high)";
  return "var(--tx)";
}

function itemIcon(item: RecentActivityItem): string {
  if (item.severity === "CRÍTICO" || item.severity === "ALTO") return "ph-fill ph-warning-octagon";
  if (item.kind === "honeyfile_created") return "ph ph-file-lock";
  if (item.kind === "endpoint_registered") return "ph ph-desktop-tower";
  return "ph ph-activity";
}

export default function RecentActivityTimeline({ items }: Props) {
  return (
    <section className="soc-panel rounded-2xl p-5 flex flex-col h-full overflow-hidden">
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-xl grid place-items-center shrink-0" style={{ background: "var(--info-soft)", color: "var(--info)" }}>
          <i className="ph ph-clock-counter-clockwise" style={{ fontSize: "18px" }} />
        </div>
        <div>
          <div className="text-[9.5px] font-bold tracking-[.15em] uppercase" style={{ color: "var(--info)" }}>
            Flujo operativo
          </div>
          <h2 className="text-[14.5px] font-semibold tracking-tight m-0 mt-1" style={{ color: "var(--tx)" }}>
            Actividad reciente
          </h2>
          <div className="text-[11px] mt-1" style={{ color: "var(--tx-mute)" }}>
            Eventos relevantes registrados por la consola
          </div>
        </div>
      </div>

      {items.length === 0 ? (
        <div className="flex-1 min-h-[190px] flex flex-col items-center justify-center text-center">
          <div className="w-10 h-10 rounded-xl grid place-items-center" style={{ background: "var(--surf2)", color: "var(--tx-mute)" }}>
            <i className="ph ph-clock" style={{ fontSize: "19px" }} />
          </div>
          <div className="text-[10.5px] mt-3" style={{ color: "var(--tx-mute)" }}>Sin actividad reciente.</div>
        </div>
      ) : (
        <div className="relative mt-4 pl-1">
          <div className="absolute top-4 bottom-4 left-[17px] w-px" style={{ background: "linear-gradient(var(--line), var(--line-soft))" }} />
          <div className="flex flex-col gap-1.5">
            {items.map((item, i) => {
              const color = dotColor(item);
              return (
                <div
                  key={i}
                  className="relative flex gap-3 px-2 py-2.5 rounded-xl"
                  style={{ background: i === 0 ? "var(--surf2)" : "transparent", border: i === 0 ? "1px solid var(--line-soft)" : "1px solid transparent" }}
                >
                  <div
                    className="relative z-[1] w-7 h-7 rounded-lg grid place-items-center shrink-0"
                    style={{ background: `color-mix(in srgb, ${color} 13%, var(--surf))`, color, border: `1px solid color-mix(in srgb, ${color} 22%, transparent)` }}
                  >
                    <i className={itemIcon(item)} style={{ fontSize: "12px" }} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <div className="text-[11px] font-semibold truncate" style={{ color: titleColor(item) }}>
                        {item.type_label}
                      </div>
                      <span className="ml-auto text-[9px] font-semibold tabular-nums shrink-0" style={{ color: "var(--tx-mute)" }}>
                        {item.time}
                      </span>
                    </div>
                    <div className="text-[9.5px] mt-1 truncate" style={{ color: "var(--tx-mute)" }}>
                      <span className="font-medium" style={{ color: "var(--tx-dim)" }}>{item.hostname}</span> · {item.label}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}
