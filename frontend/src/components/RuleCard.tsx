import { useState } from "react";
import type { HeuristicRule } from "../types/rules";
import RuleEditModal from "./RuleEditModal";

interface Props {
  rule: HeuristicRule;
  onChanged: (updated: HeuristicRule) => void;
}

function StatBlock({ label, value, valueColor, title }: { label: string; value: React.ReactNode; valueColor?: string; title?: string }) {
  return (
    <div title={title}>
      <div className="text-[10px]" style={{ color: "var(--tx-mute)" }}>{label}</div>
      <div className="text-[12.5px] font-medium mt-1 truncate" style={{ color: valueColor ?? "var(--tx-dim)" }}>{value}</div>
    </div>
  );
}

export default function RuleCard({ rule, onChanged }: Props) {
  const [editing, setEditing] = useState(false);

  const statusBadge = rule.is_deferred
    ? { text: "Diferida", bg: "var(--surf2)", color: "var(--tx-mute)", border: "1px dashed var(--line)" }
    : rule.is_active
    ? { text: "Activa", bg: "var(--ok-soft)", color: "var(--ok)", border: "1px solid var(--ok)" }
    : { text: "Inactiva", bg: "var(--surf2)", color: "var(--tx-mute)", border: "1px solid var(--line-soft)" };

  return (
    <div
      className="rounded-xl border p-5 transition-premium hover:-translate-y-1 hover:shadow-lg"
      style={{
        background: "var(--surf)",
        borderColor: rule.is_active ? "var(--line-soft)" : "var(--line)",
        boxShadow: "var(--shadow)",
        opacity: rule.is_active || rule.is_deferred ? 1 : 0.7,
      }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <div className="text-[15px] font-bold tracking-tight" style={{ color: "var(--tx)" }}>{rule.label}</div>
            {rule.is_honeyfile && (
              <span
                title="Cualquier interacción con un honeyfile lleva el riesgo directamente a CRÍTICO (risk_score 100), sin depender de otras reglas."
                className="text-[10px] font-bold tracking-wide px-2 py-0.5 rounded-full cursor-help"
                style={{ background: "var(--crit)", color: "#fff" }}
              >
                REGLA ESPECIAL &middot; CRÍTICO AUTOMÁTICO
              </span>
            )}
          </div>
          {rule.description && (
            <p className="text-[12px] mt-1 leading-relaxed" style={{ color: "var(--tx-mute)" }}>{rule.description}</p>
          )}
        </div>

        <div className="flex flex-col items-end gap-1.5 shrink-0">
          <span
            title={rule.is_deferred ? "Requiere datos que el agente no recopila hoy -- ver la descripción de la regla." : undefined}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11px] font-bold ${rule.is_deferred ? "cursor-help" : ""}`}
            style={{ background: statusBadge.bg, color: statusBadge.color, border: statusBadge.border }}
          >
            {!rule.is_deferred && <span className="w-1.5 h-1.5 rounded-full" style={{ background: rule.is_active ? "var(--ok)" : "var(--tx-mute)" }} />}
            {rule.is_deferred && <i className="ph ph-clock-countdown" style={{ fontSize: "12px" }} />}
            {statusBadge.text}
          </span>
          <button
            onClick={() => setEditing(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-bold cursor-pointer transition-premium btn-hover shadow-sm"
            style={{ border: "1px solid var(--line)", background: "var(--surf2)", color: "var(--tx-dim)" }}
          >
            <i className="ph ph-pencil-simple" style={{ fontSize: "12px" }} />
            Editar
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-3.5 pt-3.5 border-t" style={{ borderColor: "var(--line-soft)" }}>
        <StatBlock
          label="Métrica"
          value={rule.metric_type_name ?? "—"}
          title={rule.metric_type_description ?? undefined}
        />
        <StatBlock
          label="Unidad"
          value={rule.metric_unit ?? "—"}
        />
        <StatBlock
          label="Tipo de evento"
          value={rule.event_type_label}
          title={rule.event_type_description ?? undefined}
        />
        <StatBlock
          label="Estado"
          value={rule.is_active ? "Evaluándose" : "No evaluándose"}
          valueColor={rule.is_active ? "var(--ok)" : "var(--tx-mute)"}
        />

        <StatBlock
          label="Umbral"
          value={rule.has_fixed_scoring ? "No aplica" : `${rule.threshold}${rule.metric_unit ? ` ${rule.metric_unit}` : ""}`}
        />
        <StatBlock
          label="Ventana"
          value={rule.has_fixed_scoring ? "No aplica" : rule.window_seconds ? `${rule.window_seconds}s` : "—"}
        />
        <StatBlock
          label="Peso en el score"
          value={rule.is_honeyfile ? "100 (fijo)" : rule.has_fixed_scoring ? "Variable (+5/+10/+15)" : `${rule.weight} pts`}
        />
        <StatBlock
          label="Alertas (30 días)"
          value={rule.alerts_30d}
          valueColor={rule.alerts_30d > 0 ? "var(--warn)" : "var(--tx-dim)"}
        />

        <StatBlock
          label="Última activación"
          value={rule.last_triggered_at ?? "Sin actividad registrada"}
        />
        <StatBlock
          label="Creada"
          value={rule.created_at ?? "No disponible"}
        />
        <StatBlock
          label="Última actualización"
          value={rule.updated_at ?? "No disponible"}
        />
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
    </div>
  );
}
