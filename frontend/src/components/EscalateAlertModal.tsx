import { useState, useEffect } from "react";
import { escalateAlertToIncident } from "../api/client";
import type { IncidenteDrawerData } from "../types/alerts";
import { severityPillStyle } from "../lib/severity";

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

  const [entered, setEntered] = useState(false);

  // Un pequeño hack para que la animación de entrada de un modal "fijo" 
  // que no recibe 'open' desde afuera funcione. Se monta, espera un frame y entra.
  useEffect(() => {
    const raf = requestAnimationFrame(() => requestAnimationFrame(() => setEntered(true)));
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <>
      <div 
        onClick={onClose} 
        className="fixed inset-0 z-[50]" 
        style={{ background: "rgba(0,0,0,0.4)", opacity: entered ? 1 : 0, transition: "opacity 200ms ease" }} 
      />
      <div 
        className="fixed inset-0 z-[51] flex items-center justify-center p-4"
        style={{
          opacity: entered ? 1 : 0,
          transform: entered ? "scale(1)" : "scale(0.95)",
          transition: "opacity 200ms ease, transform 200ms ease",
        }}
      >
        <div
          className="w-full max-w-md rounded-2xl border flex flex-col shadow-2xl"
          style={{ background: "var(--surf)", borderColor: "var(--line-soft)" }}
        >
          <div className="px-5 py-4 border-b flex items-start gap-4" style={{ borderColor: "var(--line-soft)" }}>
            <div className="min-w-0 flex-1">
              <div className="text-[11px] tracking-wider uppercase font-semibold" style={{ color: "var(--tx-mute)" }}>
                Gestión manual
              </div>
              <div className="text-[18px] font-bold mt-1 tracking-tight truncate" style={{ color: "var(--tx)" }}>
                Escalar a incidente
              </div>
            </div>
            <button
              onClick={onClose}
              className="w-8 h-8 rounded-lg border grid place-items-center cursor-pointer transition-premium btn-hover shadow-sm"
              style={{ borderColor: "var(--line)", background: "var(--surf2)", color: "var(--tx-dim)" }}
            >
              <i className="ph-fill ph-x" style={{ fontSize: "15px" }} />
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
                      {alert.severity.toUpperCase()}
                    </span>
                  ) : (
                    "—"
                  )
                }
              />
              <Field label="Puntos de riesgo" value={alert.risk_score !== null ? alert.risk_score.toFixed(1) : "—"} />
              <Field label="Fecha" value={alert.created_at ?? "—"} />
              {alert.rules[0] && <Field label="Regla" value={alert.rules[0].rule_name} />}
            </div>
          </div>

          <div className="px-5 py-3.5 border-t flex justify-end gap-2" style={{ borderColor: "var(--line-soft)" }}>
            <button
              onClick={onClose}
              disabled={saving}
              className="px-4 py-2 rounded-lg text-[13px] font-bold cursor-pointer transition-premium btn-hover shadow-sm disabled:opacity-50"
              style={{ border: "1px solid var(--line)", color: "var(--tx-dim)", background: "var(--surf2)" }}
            >
              Cancelar
            </button>
            <button
              onClick={handleConfirm}
              disabled={saving}
              className="px-5 py-2 rounded-lg text-[13px] font-bold cursor-pointer border-0 transition-premium btn-hover shadow-sm disabled:opacity-50"
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
