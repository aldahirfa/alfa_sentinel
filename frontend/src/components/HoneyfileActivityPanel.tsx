import type { HoneyfileActivity } from "../types/dashboard";
import { textOrPlaceholder } from "../lib/placeholder";

interface Props {
  data: HoneyfileActivity;
}

export default function HoneyfileActivityPanel({ data }: Props) {
  const hasActivation = data.activated_today > 0;

  return (
    <section className="soc-panel rounded-2xl p-5 flex flex-col h-full overflow-hidden relative">
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-xl grid place-items-center shrink-0" style={{ background: "var(--info-soft)", color: "var(--info)" }}>
          <i className="ph ph-file-lock" style={{ fontSize: "18px" }} />
        </div>
        <div>
          <div className="text-[9.5px] font-bold tracking-[.15em] uppercase" style={{ color: "var(--info)" }}>
            Tecnología de engaño
          </div>
          <h2 className="text-[14.5px] font-semibold tracking-tight m-0 mt-1" style={{ color: "var(--tx)" }}>
            Actividad de honeyfiles
          </h2>
          <div className="text-[11px] mt-1" style={{ color: "var(--tx-mute)" }}>
            Estado de señuelos y últimas activaciones detectadas
          </div>
        </div>
        <a
          href="/honeyfiles"
          className="ml-auto text-[10.5px] font-semibold no-underline flex items-center gap-1.5 transition-premium btn-hover"
          style={{ color: "var(--brand)" }}
        >
          Ver honeyfiles
          <i className="ph ph-arrow-up-right" style={{ fontSize: "13px" }} />
        </a>
      </div>

      <div className="grid grid-cols-2 gap-2.5 mt-4">
        <div
          className="rounded-xl px-3.5 py-3.5 relative overflow-hidden"
          style={{ background: "var(--brand-fill)", border: "1px solid var(--brand-soft)" }}
        >
          <div className="absolute -right-3 -bottom-4 text-[52px] opacity-[.07]" style={{ color: "var(--brand)" }}>
            <i className="ph-fill ph-files" />
          </div>
          <div className="flex items-center gap-2 text-[9.5px] font-semibold uppercase tracking-wider" style={{ color: "var(--tx-mute)" }}>
            <span className="w-1.5 h-1.5 rounded-full" style={{ background: "var(--brand)" }} />
            Desplegados
          </div>
          <div className="text-[25px] font-bold mt-2 tracking-[-.04em] tabular-nums" style={{ color: "var(--tx)" }}>
            {data.active_total}
          </div>
          <div className="text-[9.5px] mt-1" style={{ color: "var(--tx-mute)" }}>honeyfiles activos</div>
        </div>

        <div
          className="rounded-xl px-3.5 py-3.5 relative overflow-hidden"
          style={{
            background: hasActivation ? "var(--warn-fill)" : "var(--surf2)",
            border: `1px solid ${hasActivation ? "var(--warn-soft)" : "var(--line-soft)"}`,
          }}
        >
          <div className="absolute -right-3 -bottom-4 text-[52px] opacity-[.07]" style={{ color: hasActivation ? "var(--warn)" : "var(--tx-mute)" }}>
            <i className="ph-fill ph-file-lock" />
          </div>
          <div className="flex items-center gap-2 text-[9.5px] font-semibold uppercase tracking-wider" style={{ color: hasActivation ? "var(--warn)" : "var(--tx-mute)" }}>
            <span className="w-1.5 h-1.5 rounded-full" style={{ background: hasActivation ? "var(--warn)" : "var(--off)" }} />
            Activados hoy
          </div>
          <div className="text-[25px] font-bold mt-2 tracking-[-.04em] tabular-nums" style={{ color: hasActivation ? "var(--warn)" : "var(--tx)" }}>
            {data.activated_today}
          </div>
          <div className="text-[9.5px] mt-1" style={{ color: "var(--tx-mute)" }}>
            {hasActivation ? "requieren revisión" : "sin actividad detectada"}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2 mt-4 mb-2.5">
        <span className="text-[9.5px] tracking-[.13em] uppercase font-bold" style={{ color: "var(--tx-mute)" }}>
          Últimas activaciones
        </span>
        <span className="flex-1 h-px" style={{ background: "var(--line-soft)" }} />
      </div>

      <div className="flex flex-col gap-1.5">
        {data.recent.length === 0 ? (
          <div className="rounded-xl py-6 text-center" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }}>
            <i className="ph ph-shield-check" style={{ fontSize: "19px", color: "var(--ok)" }} />
            <div className="text-[10.5px] mt-2" style={{ color: "var(--tx-mute)" }}>Sin activaciones registradas.</div>
          </div>
        ) : (
          data.recent.map((r, i) => (
            <div
              key={`${r.hostname}-${r.time}-${i}`}
              className="flex items-center gap-2.5 px-3 py-2.5 rounded-xl"
              style={{
                background: i === 0 ? "var(--warn-fill)" : "var(--surf2)",
                border: `1px solid ${i === 0 ? "var(--warn-soft)" : "var(--line-soft)"}`,
              }}
            >
              <div
                className="w-7 h-7 rounded-lg grid place-items-center shrink-0"
                style={{ background: i === 0 ? "var(--warn-soft)" : "var(--brand-soft)", color: i === 0 ? "var(--warn)" : "var(--brand)" }}
              >
                <i className={i === 0 ? "ph-fill ph-file-lock" : "ph ph-file-lock"} style={{ fontSize: "13px" }} />
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-[11px] font-semibold truncate" style={{ color: "var(--tx)" }}>{r.hostname}</div>
                <div className="text-[9.5px] mt-0.5 truncate mono-data" style={{ color: "var(--tx-mute)" }}>
                  {textOrPlaceholder(r.file_name)}
                </div>
              </div>
              <span className="text-[9.5px] font-semibold tabular-nums shrink-0" style={{ color: i === 0 ? "var(--warn)" : "var(--tx-mute)" }}>
                {r.time}
              </span>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
