import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import type { HeuristicRule, RuleUpdatePayload } from "../types/rules";
import { updateRule } from "../api/client";

interface Props {
  rule: HeuristicRule;
  onClose: () => void;
  onSaved: (updated: HeuristicRule) => void;
}

const fieldStyle: React.CSSProperties = {
  background: "var(--surf2)",
  border: "1px solid var(--line-soft)",
  color: "var(--tx)",
};

function ContextRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between text-[12.5px] py-1">
      <span style={{ color: "var(--tx-mute)" }}>{label}</span>
      <span className="font-medium text-right" style={{ color: "var(--tx)" }}>{value}</span>
    </div>
  );
}

// Modal de edición de una regla heurística -- mismo patrón visual que
// UserFormModal.tsx (overlay + tarjeta centrada, header eyebrow +
// título + X, cuerpo con inputs, footer Cancelar/Guardar). Los campos
// no editables (nombre, métrica, evento, descripción) se muestran como
// contexto de solo lectura arriba de los editables, nunca mezclados.
export default function RuleEditModal({ rule, onClose, onSaved }: Props) {
  const [weight, setWeight] = useState(String(rule.weight));
  const [threshold, setThreshold] = useState(String(rule.threshold));
  const [windowSeconds, setWindowSeconds] = useState(String(rule.window_seconds ?? ""));
  const [isActive, setIsActive] = useState(rule.is_active);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [entered, setEntered] = useState(false);
  useEffect(() => {
    const raf = requestAnimationFrame(() => requestAnimationFrame(() => setEntered(true)));
    return () => cancelAnimationFrame(raf);
  }, []);

  async function handleSave() {
    setError(null);

    const payload: RuleUpdatePayload = {};

    if (isActive !== rule.is_active) payload.is_active = isActive;

    if (!rule.has_fixed_scoring) {
      const w = Number(weight);
      const t = Number(threshold);
      const win = Number(windowSeconds);

      if (String(w) !== String(rule.weight)) {
        if (Number.isNaN(w) || w < 0 || w > 100) {
          setError("El peso tiene que ser un número entre 0 y 100.");
          return;
        }
        payload.weight = w;
      }
      if (String(t) !== String(rule.threshold)) {
        if (Number.isNaN(t) || t <= 0) {
          setError("El umbral tiene que ser un número mayor a 0.");
          return;
        }
        payload.threshold = t;
      }
      if (String(win) !== String(rule.window_seconds ?? "")) {
        if (Number.isNaN(win) || win <= 0) {
          setError("La ventana tiene que ser un número de segundos mayor a 0.");
          return;
        }
        payload.window_seconds = win;
      }
    }

    if (Object.keys(payload).length === 0) {
      onClose();
      return;
    }

    setSaving(true);
    try {
      const res = await updateRule(rule.id, payload);
      onSaved({
        ...rule,
        weight: res.weight,
        threshold: res.threshold,
        window_seconds: res.window_seconds,
        is_active: res.is_active,
        updated_at: res.updated_at,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo guardar la regla.");
    } finally {
      setSaving(false);
    }
  }

  // Se monta con un portal (a diferencia de UserFormModal, que no lo
  // necesita) porque este modal se abre desde RuleCard.tsx, cuyo
  // contenedor tiene "hover:-translate-y-1". Cualquier transform en un
  // ancestro crea un nuevo "containing block" para position:fixed -- sin el
  // portal, el overlay/modal quedaban fijados relativo a esa tarjeta (con
  // hover activo) en vez del viewport real, por eso reglas más abajo en la
  // página aparecían con el modal cortado/desplazado.
  //
  // El portal apunta a #app-shell (App.tsx), NO a document.body: las
  // variables CSS del tema (--surf, --tx, --line-soft, etc.) se definen
  // vía [data-theme] en ese div, no en <html>/<body>. Un portal directo a
  // document.body queda fuera de su alcance -- var(--surf) no resuelve a
  // nada ahí, y el modal se veía con fondo transparente. #app-shell no
  // tiene transform propio, así que sigue resolviendo el bug original de
  // posicionamiento igual que un portal a body.
  const portalTarget = document.getElementById("app-shell") ?? document.body;

  return createPortal(
    <>
      <div
        onClick={onClose}
        className="fixed inset-0 z-40"
        style={{ background: "rgba(0,0,0,0.4)", opacity: entered ? 1 : 0, transition: "opacity 200ms ease" }}
      />
      <div
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
        style={{
          opacity: entered ? 1 : 0,
          transform: entered ? "scale(1)" : "scale(0.95)",
          transition: "opacity 200ms ease, transform 200ms ease",
        }}
      >
        <div
          className="w-full max-w-md rounded-2xl border flex flex-col shadow-2xl max-h-[90vh]"
          style={{ background: "var(--surf)", borderColor: "var(--line-soft)" }}
        >
          <div className="px-5 py-4 border-b flex items-start gap-4 shrink-0" style={{ borderColor: "var(--line-soft)" }}>
            <div className="min-w-0 flex-1">
              <div className="text-[11px] tracking-wider uppercase font-semibold" style={{ color: "var(--tx-mute)" }}>
                Reglas heurísticas
              </div>
              <div className="text-[18px] font-bold mt-1 tracking-tight truncate" style={{ color: "var(--tx)" }}>
                {rule.label}
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

          <div className="px-5 py-4 flex flex-col gap-3.5 overflow-y-auto">
            {error && (
              <div className="rounded-[8px] px-3 py-2 text-[12px]" style={{ background: "var(--crit-soft)", color: "var(--crit)" }}>
                {error}
              </div>
            )}

            <div className="rounded-[10px] p-3.5 flex flex-col gap-1" style={{ background: "var(--surf2)" }}>
              <div className="text-[11px] font-bold tracking-wide uppercase mb-1" style={{ color: "var(--tx-mute)" }}>Contexto (no editable)</div>
              <ContextRow label="Regla" value={rule.name} />
              <ContextRow label="Métrica" value={`${rule.metric_type_name ?? "—"}${rule.metric_unit ? ` (${rule.metric_unit})` : ""}`} />
              <ContextRow label="Evento" value={rule.event_type_label} />
            </div>

            {rule.is_honeyfile && (
              <div className="rounded-[10px] p-3.5 flex flex-col gap-2" style={{ background: "var(--crit-soft)", border: "1px solid var(--crit)" }}>
                <p className="text-[12.5px] leading-relaxed font-medium" style={{ color: "var(--tx)" }}>
                  Esta regla clasifica automáticamente la actividad como CRÍTICA cuando se detecta cualquier
                  interacción con un honeyfile -- no depende de un peso ni de un umbral configurable.
                </p>
                <ContextRow label="Puntos de riesgo resultantes" value={<span style={{ color: "var(--crit)" }}>100</span>} />
                <ContextRow label="Severidad" value={<span style={{ color: "var(--crit)" }}>CRÍTICO</span>} />
              </div>
            )}

            {!rule.is_honeyfile && rule.has_fixed_scoring && (
              <div className="rounded-[10px] p-3.5" style={{ background: "var(--info-soft)", border: "1px solid var(--info)" }}>
                <p className="text-[12.5px] leading-relaxed font-medium" style={{ color: "var(--tx)" }}>
                  Esta regla no puntúa por umbral/ventana: es una bonificación de correlación que el servidor
                  calcula según cuántas reglas distintas coincidieron en el mismo episodio (2 reglas → +5,
                  3 → +10, 4 o más → +15). Solo se puede activar o desactivar.
                </p>
              </div>
            )}

            {!rule.has_fixed_scoring && (
              <div className="grid grid-cols-3 gap-2.5">
                <div>
                  <label className="text-[11.5px] font-semibold block mb-1.5" style={{ color: "var(--tx-mute)" }}>Weight</label>
                  <input
                    type="number" min={0} max={100} step={1}
                    value={weight}
                    onChange={(e) => setWeight(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg text-[13px] font-bold tabular-nums outline-none transition-premium focus:ring-2 focus:ring-[var(--brand)] focus:border-transparent"
                    style={fieldStyle}
                  />
                  <p className="text-[10px] mt-1" style={{ color: "var(--tx-mute)" }}>puntos</p>
                </div>
                <div>
                  <label className="text-[11.5px] font-semibold block mb-1.5" style={{ color: "var(--tx-mute)" }}>Threshold</label>
                  <input
                    type="number" min={0} step={1}
                    value={threshold}
                    onChange={(e) => setThreshold(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg text-[13px] font-bold tabular-nums outline-none transition-premium focus:ring-2 focus:ring-[var(--brand)] focus:border-transparent"
                    style={fieldStyle}
                  />
                  <p className="text-[10px] mt-1" style={{ color: "var(--tx-mute)" }}>{rule.metric_unit ?? "unidades"}</p>
                </div>
                <div>
                  <label className="text-[11.5px] font-semibold block mb-1.5" style={{ color: "var(--tx-mute)" }}>Window</label>
                  <input
                    type="number" min={0} step={1}
                    value={windowSeconds}
                    onChange={(e) => setWindowSeconds(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg text-[13px] font-bold tabular-nums outline-none transition-premium focus:ring-2 focus:ring-[var(--brand)] focus:border-transparent"
                    style={fieldStyle}
                  />
                  <p className="text-[10px] mt-1" style={{ color: "var(--tx-mute)" }}>segundos</p>
                </div>
              </div>
            )}

            <label
              className="flex items-center gap-2 text-[13px]"
              style={{ color: rule.is_deferred ? "var(--tx-mute)" : "var(--tx)", cursor: rule.is_deferred ? "not-allowed" : "pointer" }}
              title={rule.is_deferred ? "Diferida: requiere datos que el agente no recopila hoy. No se puede activar todavía." : undefined}
            >
              <input
                type="checkbox"
                checked={isActive}
                disabled={rule.is_deferred && !isActive}
                onChange={(e) => setIsActive(e.target.checked)}
              />
              Regla activa
            </label>
          </div>

          <div className="px-5 py-3.5 border-t flex justify-end gap-2 shrink-0" style={{ borderColor: "var(--line-soft)" }}>
            <button
              onClick={onClose}
              disabled={saving}
              className="px-4 py-2 rounded-lg text-[13px] font-bold cursor-pointer transition-premium btn-hover shadow-sm disabled:opacity-50"
              style={{ border: "1px solid var(--line)", color: "var(--tx-dim)", background: "var(--surf2)" }}
            >
              Cancelar
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-5 py-2 rounded-lg text-[13px] font-bold cursor-pointer border-0 transition-premium btn-hover shadow-sm disabled:opacity-50"
              style={{ background: "var(--brand)", color: "#fff" }}
            >
              {saving ? "Guardando..." : "Guardar cambios"}
            </button>
          </div>
        </div>
      </div>
    </>,
    portalTarget
  );
}
