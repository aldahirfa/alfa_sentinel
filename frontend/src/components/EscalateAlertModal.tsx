import { useState } from "react";
import { escalateAlertToIncident } from "../api/client";
import type { IncidenteDrawerData } from "../types/alerts";
import { SEVERITY_LABEL, severityPillStyle } from "../lib/severity";

interface Props {
  alert: IncidenteDrawerData;
  onClose: () => void;
  onEscalated: () => void;
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between text-[12.5px] py-1">
      <span style={{ color: "var(--tx-mute)" }}>{label}</span>
      <span className="font-medium text-right" style={{ color: "var(--tx)" }}>{value}</span>
    </div>
  );
}

// Confirmación antes de crear un incidente a partir de una alerta
// (escalamiento manual, distinto del automático que ya hace el motor
// heurístico -- ver server/main.py::create_incident, POST /incidents,
// reusado tal cual, no se creó ningún endpoint nuevo).
export default function EscalateAlertModal({ alert, onClose, onEscalated }: Props) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleConfirm() {
    setSaving(true);
    setError(null);
    try {
      await escalateAlertToIncident(alert.id);
      onEscalated();
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo escalar la alerta a incidente.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <div onClick={onClose} className="fixed inset-0 z-50" style={{ background: "rgba(0,0,0,0.5)" }} />
      <div className="fixed inset-0 z-[51] flex items-center justify-center p-4">
        <div
          className="w-full max-w-md rounded-[12px] border flex flex-col"
          style={{ background: "var(--surf)", borderColor: "var(--line)", boxShadow: "0 20px 60px rgba(0,0,0,.4)" }}
        >
          <div className="px-5 py-4 border-b flex items-center justify-between" style={{ borderColor: "var(--line-soft)" }}>
            <div className="text-[15px] font-semibold" style={{ color: "var(--tx)" }}>Escalar a incidente</div>
            <button
              onClick={onClose}
              className="w-8 h-8 rounded-lg border grid place-items-center cursor-pointer"
              style={{ borderColor: "var(--line)", background: "var(--surf2)", color: "var(--tx-dim)" }}
            >
              <i className="ph ph-x" style={{ fontSize: "15px" }} />
            </button>
          </div>

          <div className="px-5 py-4 flex flex-col gap-3">
            <p className="text-[12.5px] leading-relaxed" style={{ color: "var(--tx-dim)" }}>
              Esta alerta se convertirá en un incidente para su investigación y gestión. El mecanismo automático de
              detección sigue funcionando igual -- esto es una acción de gestión adicional, no lo reemplaza.
            </p>

            {error && (
              <div className="rounded-[8px] px-3 py-2 text-[12px]" style={{ background: "var(--crit-soft)", color: "var(--crit)" }}>
                {error}
              </div>
            )}

            <div className="rounded-[10px] p-3.5 flex flex-col gap-1" style={{ background: "var(--surf2)" }}>
              <div className="text-[13px] font-semibold mb-1.5" style={{ color: "var(--tx)" }}>{alert.title}</div>
              <Field label="Endpoint" value={alert.hostname} />
              <Field
                label="Severidad"
                value={
                  alert.severity ? (
                    <span
                      className="text-[10.5px] font-bold tracking-wide px-1.5 py-0.5 rounded"
                      style={severityPillStyle(alert.severity)}
                    >
                      {SEVERITY_LABEL[alert.severity].toUpperCase()}
                    </span>
                  ) : (
                    "—"
                  )
                }
              />
              <Field label="Risk score" value={alert.risk_score !== null ? alert.risk_score.toFixed(1) : "—"} />
              <Field label="Fecha" value={alert.created_at ?? "—"} />
              {alert.rules[0] && <Field label="Regla" value={alert.rules[0].rule_name} />}
            </div>
          </div>

          <div className="px-5 py-3.5 border-t flex justify-end gap-2" style={{ borderColor: "var(--line-soft)" }}>
            <button
              onClick={onClose}
              disabled={saving}
              className="px-3.5 py-2 rounded-[8px] text-[12.5px] font-medium cursor-pointer disabled:opacity-50"
              style={{ border: "1px solid var(--line)", color: "var(--tx-dim)", background: "var(--surf2)" }}
            >
              Cancelar
            </button>
            <button
              onClick={handleConfirm}
              disabled={saving}
              className="px-4 py-2 rounded-[8px] text-[12.5px] font-semibold cursor-pointer border-0 disabled:opacity-50"
              style={{ background: "var(--brand)", color: "#fff" }}
            >
              {saving ? "Escalando..." : "Confirmar escalamiento"}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
