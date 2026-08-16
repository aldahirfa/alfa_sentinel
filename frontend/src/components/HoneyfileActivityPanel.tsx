import type { HoneyfileActivity } from "../types/dashboard";
import { textOrPlaceholder } from "../lib/placeholder";

interface Props {
  data: HoneyfileActivity;
}

export default function HoneyfileActivityPanel({ data }: Props) {
  return (
    <section
      className="rounded-xl border p-5 shadow-sm flex flex-col h-full"
      style={{ background: "var(--surf)", borderColor: "var(--line-soft)" }}
    >
      <div className="flex items-center">
        <h2 className="text-[14px] font-bold tracking-tight m-0" style={{ color: "var(--tx)" }}>
          Actividad de honeyfiles
        </h2>
        <a
          href="/honeyfiles"
          className="ml-auto text-xs font-bold no-underline flex items-center gap-1 transition-premium btn-hover"
          style={{ color: "var(--brand)" }}
        >
          Ver honeyfiles
          <i className="ph-fill ph-arrow-right text-[13px]" />
        </a>
      </div>

      <div className="grid grid-cols-2 gap-2.5 mt-3.5">
        <div className="rounded-[9px] px-3 py-3" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }}>
          <div className="text-[11px]" style={{ color: "var(--tx-mute)" }}>Honeyfiles activos</div>
          <div className="text-2xl font-semibold mt-1 tracking-tight" style={{ color: "var(--tx)" }}>
            {data.active_total}
          </div>
        </div>
        <div
          className="rounded-[9px] px-3 py-3"
          style={{
            background: data.activated_today > 0 ? "var(--warn-soft)" : "var(--surf2)",
            border: `1px solid ${data.activated_today > 0 ? "var(--warn-soft)" : "var(--line-soft)"}`,
          }}
        >
          <div className="text-[11px]" style={{ color: data.activated_today > 0 ? "var(--warn)" : "var(--tx-mute)" }}>
            Activados hoy
          </div>
          <div
            className="text-2xl font-semibold mt-1 tracking-tight"
            style={{ color: data.activated_today > 0 ? "var(--warn)" : "var(--tx)" }}
          >
            {data.activated_today}
          </div>
        </div>
      </div>

      <div className="text-[10.5px] tracking-wider uppercase font-semibold mt-4" style={{ color: "var(--tx-mute)" }}>
        Últimas activaciones
      </div>
      <div className="flex flex-col gap-1.5 mt-2.5">
        {data.recent.length === 0 ? (
          <p className="text-xs text-center py-4" style={{ color: "var(--tx-mute)" }}>
            Sin activaciones registradas.
          </p>
        ) : (
          data.recent.map((r, i) => (
            <div
              key={`${r.hostname}-${r.time}-${i}`}
              className="flex items-center gap-2.5 px-2.5 py-2 rounded-lg"
              style={i === 0 ? { background: "var(--warn-soft)", boxShadow: "inset 3px 0 0 var(--warn)" } : { background: "var(--surf2)" }}
            >
              <span
                className="text-[11.5px] font-semibold tabular-nums"
                style={{ color: i === 0 ? "var(--warn)" : "var(--tx-mute)" }}
              >
                {r.time}
              </span>
              <span className="text-[12.5px] font-medium" style={{ color: "var(--tx)" }}>{r.hostname}</span>
              <span
                className="ml-auto text-xs flex items-center gap-1.5 truncate"
                style={{ color: "var(--tx-dim)" }}
              >
                <i className={i === 0 ? "ph-fill ph-file-lock" : "ph ph-file-lock"} style={{ fontSize: "13px", color: i === 0 ? "var(--warn)" : undefined }} />
                {textOrPlaceholder(r.file_name)}
              </span>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
