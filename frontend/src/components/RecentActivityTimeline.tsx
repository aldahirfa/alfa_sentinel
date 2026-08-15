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
  if (item.severity === "CRITICAL") return "var(--crit)";
  if (item.severity === "HIGH") return "var(--high)";
  return "var(--tx)";
}

export default function RecentActivityTimeline({ items }: Props) {
  return (
    <section
      className="rounded-[10px] border p-4"
      style={{ background: "var(--surf)", borderColor: "var(--line)", boxShadow: "var(--shadow)" }}
    >
      <h2 className="text-[14.5px] font-semibold m-0" style={{ color: "var(--tx)" }}>Actividad reciente</h2>

      {items.length === 0 ? (
        <p className="text-[12.5px] py-6 text-center" style={{ color: "var(--tx-mute)" }}>
          Sin actividad todavía.
        </p>
      ) : (
        <div className="flex flex-col mt-3.5">
          {items.map((item, i) => {
            const isLast = i === items.length - 1;
            return (
              <div key={i} className="flex gap-3">
                <div className="w-[38px] shrink-0 text-right text-[11.5px] tabular-nums pt-px" style={{ color: "var(--tx-mute)" }}>
                  {item.time}
                </div>
                <div className="w-[9px] shrink-0 flex flex-col items-center">
                  <span className="w-[9px] h-[9px] rounded-full mt-1.5" style={{ background: dotColor(item) }} />
                  {!isLast && <span className="flex-1 w-px" style={{ background: "var(--line)" }} />}
                </div>
                <div className={isLast ? "" : "pb-4"}>
                  <div className="text-[12.5px] font-medium" style={{ color: titleColor(item) }}>
                    {item.type_label}
                  </div>
                  <div className="text-[11.5px] mt-0.5" style={{ color: "var(--tx-mute)" }}>
                    {item.hostname} · {item.label}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
