import { useState } from "react";
import type { HeuristicRule } from "../types/rules";
import RuleEditModal from "./RuleEditModal";

interface Props {
  rule: HeuristicRule;
  onChanged: (updated: HeuristicRule) => void;
}

function StatBlock({ label, value, valueColor, title, icon }: { label: string; value: React.ReactNode; valueColor?: string; title?: string; icon: string }) {
  return (
    <div title={title} className="rounded-xl border px-3 py-3 min-w-0" style={{ background: "var(--surf2)", borderColor: "var(--line-soft)" }}>
      <div className="flex items-center gap-1.5 text-[8.5px] font-semibold uppercase tracking-[.1em]" style={{ color: "var(--tx-mute)" }}>
        <i className={icon} style={{ fontSize: "11px" }} />
        {label}
      </div>
      <div className="text-[11px] font-semibold mt-1.5 truncate" style={{ color: valueColor ?? "var(--tx-dim)" }}>{value}</div>
    </div>
  );
}

export default function RuleCard({ rule, onChanged }: Props) {
  const [editing, setEditing] = useState(false);
  const tone = rule.is_honeyfile ? "var(--crit)" : rule.is_active ? "var(--brand)" : "var(--off)";
  const statusBadge = rule.is_deferred
    ? { text: "Diferida", bg: "var(--surf3)", color: "var(--tx-mute)", border: "var(--line)" }
    : rule.is_active
      ? { text: "Activa", bg: "var(--ok-soft)", color: "var(--ok)", border: "color-mix(in srgb, var(--ok) 30%, var(--line-soft))" }
      : { text: "Inactiva", bg: "var(--surf3)", color: "var(--tx-mute)", border: "var(--line-soft)" };

  return (
    <section
      className="soc-panel rounded-2xl overflow-hidden transition-premium hover:-translate-y-[1px]"
      style={{ opacity: rule.is_active || rule.is_deferred ? 1 : .72 }}
    >
      <div className="h-px" style={{ background: `linear-gradient(90deg, ${tone}, transparent 72%)`, opacity: .7 }} />
      <div className="p-5">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-2xl grid place-items-center shrink-0" style={{ background: `color-mix(in srgb, ${tone} 11%, var(--surf2))`, color: tone }}>
            <i className={rule.is_honeyfile ? "ph-fill ph-file-lock" : "ph ph-function"} style={{ fontSize: "18px" }} />
          </div>

          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="mono-data text-[8.5px] font-bold px-2 py-1 rounded-lg" style={{ background: "var(--surf3)", color: "var(--tx-mute)" }}>{rule.name}</span>
              {rule.is_honeyfile && (
                <span className="text-[8.5px] font-bold tracking-[.08em] px-2 py-1 rounded-lg" style={{ background: "var(--crit-soft)", color: "var(--crit)", border: "1px solid var(--crit-soft)" }}>
                  CRÍTICO AUTOMÁTICO
                </span>
              )}
            </div>
            <h3 className="m-0 mt-2 text-[15px] font-semibold tracking-tight" style={{ color: "var(--tx)" }}>{rule.label}</h3>
            {rule.description && <p className="m-0 mt-1.5 text-[10.5px] leading-relaxed" style={{ color: "var(--tx-mute)" }}>{rule.description}</p>}
          </div>

          <span
            title={rule.is_deferred ? "La regla requiere datos que el agente no recopila actualmente." : undefined}
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl text-[9px] font-semibold shrink-0"
            style={{ background: statusBadge.bg, color: statusBadge.color, border: `1px solid ${statusBadge.border}` }}
          >
            <span className="w-1.5 h-1.5 rounded-full" style={{ background: statusBadge.color }} />
            {statusBadge.text}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2.5 mt-4">
          <StatBlock icon="ph ph-gauge" label="Métrica" value={rule.metric_type_name ?? "No disponible"} title={rule.metric_type_description ?? undefined} />
          <StatBlock icon="ph ph-waveform" label="Evento" value={rule.event_type_label} title={rule.event_type_description ?? undefined} />
          <StatBlock icon="ph ph-target" label="Umbral" value={rule.has_fixed_scoring ? "No aplica" : `${rule.threshold}${rule.metric_unit ? ` ${rule.metric_unit}` : ""}`} />
          <StatBlock icon="ph ph-clock" label="Ventana" value={rule.has_fixed_scoring ? "No aplica" : rule.window_seconds ? `${rule.window_seconds} s` : "—"} />
          <StatBlock icon="ph ph-scales" label="Peso en score" value={rule.is_honeyfile ? "100 pts · fijo" : rule.has_fixed_scoring ? "Variable +5/+10/+15" : `${rule.weight} pts`} valueColor={rule.is_honeyfile ? "var(--crit)" : "var(--brand)"} />
          <StatBlock icon="ph ph-warning" label="Alertas · 30 días" value={rule.alerts_30d} valueColor={rule.alerts_30d > 0 ? "var(--warn)" : "var(--tx-dim)"} />
        </div>

        <div className="flex items-center gap-3 mt-4 pt-4 border-t flex-wrap" style={{ borderColor: "var(--line-soft)" }}>
          <div className="min-w-0 flex-1">
            <div className="text-[8.5px] font-semibold uppercase tracking-[.1em]" style={{ color: "var(--tx-mute)" }}>Última activación</div>
            <div className="text-[9.5px] mt-1 truncate" style={{ color: "var(--tx-dim)" }}>{rule.last_triggered_at ?? "Sin actividad registrada"}</div>
          </div>
          <div className="hidden sm:block w-px h-8" style={{ background: "var(--line-soft)" }} />
          <div className="min-w-0 flex-1">
            <div className="text-[8.5px] font-semibold uppercase tracking-[.1em]" style={{ color: "var(--tx-mute)" }}>Última actualización</div>
            <div className="text-[9.5px] mt-1 truncate" style={{ color: "var(--tx-dim)" }}>{rule.updated_at ?? "No disponible"}</div>
          </div>
          <button
            onClick={() => setEditing(true)}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-[10px] font-semibold cursor-pointer transition-premium btn-hover border"
            style={{ borderColor: "var(--brand-soft)", background: "var(--brand-fill)", color: "var(--brand)" }}
          >
            <i className="ph ph-sliders-horizontal" style={{ fontSize: "13px" }} />
            Configurar regla
          </button>
        </div>
      </div>

      {editing && (
        <RuleEditModal
          rule={rule}
          onClose={() => setEditing(false)}
          onSaved={(updated) => {
            onChanged(updated);
            setEditing(false);
          }}
        />
      )}
    </section>
  );
}
