import { useState, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import type { AgentRuleItem, AgentRuleUpdatePayload } from "../types/agentRules";
import { fetchAgentRules, updateAgentRule, deleteAgentRuleOverride } from "../api/client";

interface Props {
  agentId: number;
  hostnameHint?: string;
  onClose: () => void;
}

const fieldStyle: React.CSSProperties = {
  background: "var(--surf2)",
  border: "1px solid var(--line-soft)",
  color: "var(--tx)",
};

function SummaryPair({
  label,
  globalValue,
  effectiveValue,
  customized,
}: {
  label: string;
  globalValue: React.ReactNode;
  effectiveValue: React.ReactNode;
  customized: boolean;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] uppercase tracking-wide font-semibold" style={{ color: "var(--tx-mute)" }}>
        {label}
      </span>
      <span className="text-[13px] font-bold tabular-nums" style={{ color: customized ? "var(--brand)" : "var(--tx)" }}>
        {effectiveValue}
      </span>
      {customized && (
        <span className="text-[10.5px]" style={{ color: "var(--tx-mute)" }}>
          Global: {globalValue}
        </span>
      )}
    </div>
  );
}

// Una fila por regla -- estado de edición propio (no se comparte con
// las demás filas) porque cada regla se guarda/borra de forma
// independiente contra PATCH/DELETE /api/agents/{agent_id}/rules/{rule_id}.
function AgentRuleRow({
  rule,
  agentId,
  onUpdated,
}: {
  rule: AgentRuleItem;
  agentId: number;
  onUpdated: (updated: AgentRuleItem) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [weightInput, setWeightInput] = useState(String(rule.override?.weight ?? ""));
  const [thresholdInput, setThresholdInput] = useState(String(rule.override?.threshold ?? ""));
  const [windowInput, setWindowInput] = useState(String(rule.override?.window_seconds ?? ""));
  const [isActiveChecked, setIsActiveChecked] = useState(rule.effective.is_active);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function resetFormToRule(r: AgentRuleItem) {
    setWeightInput(String(r.override?.weight ?? ""));
    setThresholdInput(String(r.override?.threshold ?? ""));
    setWindowInput(String(r.override?.window_seconds ?? ""));
    setIsActiveChecked(r.effective.is_active);
    setError(null);
  }

  async function handleSave() {
    setError(null);

    // Semántica NULL-significativo (ver types/agentRules.ts): un campo
    // se manda solo si el valor deseado cambia respecto al override
    // actual -- vacío = null explícito (volver a heredar el global),
    // un número = override puntual. is_active siempre se manda
    // explícito: la columna no admite NULL, así que "no tocarlo" solo
    // tiene sentido cuando ya coincide con lo que había.
    const payload: AgentRuleUpdatePayload = {};

    if (isActiveChecked !== rule.effective.is_active || rule.override?.is_active !== isActiveChecked) {
      payload.is_active = isActiveChecked;
    }

    if (!rule.has_fixed_scoring) {
      const currentWeight = rule.override?.weight ?? null;
      const currentThreshold = rule.override?.threshold ?? null;
      const currentWindow = rule.override?.window_seconds ?? null;

      const desiredWeight = weightInput.trim() === "" ? null : Number(weightInput);
      const desiredThreshold = thresholdInput.trim() === "" ? null : Number(thresholdInput);
      const desiredWindow = windowInput.trim() === "" ? null : Number(windowInput);

      if (desiredWeight !== currentWeight) {
        if (desiredWeight !== null && (Number.isNaN(desiredWeight) || desiredWeight < 0)) {
          setError("El peso tiene que ser un número mayor o igual a 0, o quedar vacío para heredar el global.");
          return;
        }
        payload.weight = desiredWeight;
      }
      if (desiredThreshold !== currentThreshold) {
        if (desiredThreshold !== null && (Number.isNaN(desiredThreshold) || desiredThreshold < 0)) {
          setError("El umbral tiene que ser un número mayor o igual a 0, o quedar vacío para heredar el global.");
          return;
        }
        payload.threshold = desiredThreshold;
      }
      if (desiredWindow !== currentWindow) {
        if (desiredWindow !== null && (Number.isNaN(desiredWindow) || desiredWindow <= 0)) {
          setError("La ventana tiene que ser un número de segundos mayor a 0, o quedar vacía para heredar el global.");
          return;
        }
        payload.window_seconds = desiredWindow;
      }
    }

    if (Object.keys(payload).length === 0) {
      setExpanded(false);
      return;
    }

    setSaving(true);
    try {
      const res = await updateAgentRule(agentId, rule.id, payload);
      const updated: AgentRuleItem = {
        ...rule,
        override: res.override,
        has_override: true,
        effective: {
          weight: res.override.weight ?? rule.global.weight,
          threshold: res.override.threshold ?? rule.global.threshold,
          window_seconds: res.override.window_seconds ?? rule.global.window_seconds,
          is_active: res.override.is_active,
        },
      };
      onUpdated(updated);
      resetFormToRule(updated);
      setExpanded(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo guardar la configuración.");
    } finally {
      setSaving(false);
    }
  }

  async function handleRemoveOverride() {
    setError(null);
    setSaving(true);
    try {
      await deleteAgentRuleOverride(agentId, rule.id);
      const updated: AgentRuleItem = {
        ...rule,
        override: null,
        has_override: false,
        effective: { ...rule.global },
      };
      onUpdated(updated);
      resetFormToRule(updated);
      setExpanded(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo quitar la configuración personalizada.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="rounded-[10px] border" style={{ borderColor: "var(--line-soft)", background: "var(--surf2)" }}>
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between gap-3 px-3.5 py-3 text-left cursor-pointer"
      >
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-[13px] font-bold truncate" style={{ color: "var(--tx)" }}>
              {rule.name}
            </span>
            {rule.has_override && (
              <span
                className="text-[9.5px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded-full shrink-0"
                style={{ background: "var(--brand-soft, rgba(99,102,241,0.15))", color: "var(--brand)" }}
              >
                Personalizado
              </span>
            )}
            <span
              className="text-[9.5px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded-full shrink-0"
              style={{
                background: rule.effective.is_active ? "var(--ok-soft, rgba(34,197,94,0.15))" : "var(--surf)",
                color: rule.effective.is_active ? "var(--ok, #22c55e)" : "var(--tx-mute)",
              }}
            >
              {rule.effective.is_active ? "Activa" : "Inactiva"}
            </span>
          </div>
          {!rule.has_fixed_scoring && (
            <div className="flex gap-4 mt-2">
              <SummaryPair
                label="Peso"
                globalValue={rule.global.weight}
                effectiveValue={rule.effective.weight}
                customized={rule.override?.weight != null}
              />
              <SummaryPair
                label="Umbral"
                globalValue={rule.global.threshold}
                effectiveValue={rule.effective.threshold}
                customized={rule.override?.threshold != null}
              />
              <SummaryPair
                label="Ventana"
                globalValue={rule.global.window_seconds ?? "—"}
                effectiveValue={rule.effective.window_seconds ?? "—"}
                customized={rule.override?.window_seconds != null}
              />
            </div>
          )}
        </div>
        <i
          className={`ph-fill ${expanded ? "ph-caret-up" : "ph-caret-down"} shrink-0`}
          style={{ fontSize: "14px", color: "var(--tx-mute)" }}
        />
      </button>

      {expanded && (
        <div className="px-3.5 pb-3.5 flex flex-col gap-3 border-t" style={{ borderColor: "var(--line-soft)" }}>
          <div className="pt-3" />

          {error && (
            <div className="rounded-[8px] px-3 py-2 text-[12px]" style={{ background: "var(--crit-soft)", color: "var(--crit)" }}>
              {error}
            </div>
          )}

          {rule.has_fixed_scoring && (
            <p className="text-[12px] leading-relaxed" style={{ color: "var(--tx-mute)" }}>
              Esta regla no puntúa por umbral/ventana ({rule.is_honeyfile ? "peso fijo 100" : "bonificación de correlación"}
              ) -- para este endpoint solo se puede activar o desactivar.
            </p>
          )}

          {!rule.has_fixed_scoring && (
            <div className="grid grid-cols-3 gap-2.5">
              <div>
                <label className="text-[11px] font-semibold block mb-1.5" style={{ color: "var(--tx-mute)" }}>
                  Weight
                </label>
                <input
                  type="number" min={0} step={1}
                  placeholder={`Global: ${rule.global.weight}`}
                  value={weightInput}
                  onChange={(e) => setWeightInput(e.target.value)}
                  className="w-full px-2.5 py-1.5 rounded-lg text-[12.5px] font-bold tabular-nums outline-none transition-premium focus:ring-2 focus:ring-[var(--brand)] focus:border-transparent"
                  style={fieldStyle}
                />
              </div>
              <div>
                <label className="text-[11px] font-semibold block mb-1.5" style={{ color: "var(--tx-mute)" }}>
                  Threshold
                </label>
                <input
                  type="number" min={0} step={1}
                  placeholder={`Global: ${rule.global.threshold}`}
                  value={thresholdInput}
                  onChange={(e) => setThresholdInput(e.target.value)}
                  className="w-full px-2.5 py-1.5 rounded-lg text-[12.5px] font-bold tabular-nums outline-none transition-premium focus:ring-2 focus:ring-[var(--brand)] focus:border-transparent"
                  style={fieldStyle}
                />
              </div>
              <div>
                <label className="text-[11px] font-semibold block mb-1.5" style={{ color: "var(--tx-mute)" }}>
                  Window
                </label>
                <input
                  type="number" min={0} step={1}
                  placeholder={`Global: ${rule.global.window_seconds ?? "—"}`}
                  value={windowInput}
                  onChange={(e) => setWindowInput(e.target.value)}
                  className="w-full px-2.5 py-1.5 rounded-lg text-[12.5px] font-bold tabular-nums outline-none transition-premium focus:ring-2 focus:ring-[var(--brand)] focus:border-transparent"
                  style={fieldStyle}
                />
              </div>
            </div>
          )}
          {!rule.has_fixed_scoring && (
            <p className="text-[10.5px] -mt-1.5" style={{ color: "var(--tx-mute)" }}>
              Vacío = usar el valor global para ese campo.
            </p>
          )}

          <label
            className="flex items-center gap-2 text-[12.5px]"
            style={{ color: rule.is_deferred ? "var(--tx-mute)" : "var(--tx)", cursor: rule.is_deferred ? "not-allowed" : "pointer" }}
            title={rule.is_deferred ? "Diferida: requiere datos que el agente no recopila hoy." : undefined}
          >
            <input
              type="checkbox"
              checked={isActiveChecked}
              disabled={rule.is_deferred && !isActiveChecked}
              onChange={(e) => setIsActiveChecked(e.target.checked)}
            />
            Regla activa en este endpoint
          </label>

          <div className="flex justify-between items-center gap-2 pt-1">
            {rule.has_override ? (
              <button
                onClick={handleRemoveOverride}
                disabled={saving}
                className="px-3 py-1.5 rounded-lg text-[12px] font-bold cursor-pointer transition-premium btn-hover disabled:opacity-50"
                style={{ border: "1px solid var(--line)", color: "var(--tx-dim)", background: "var(--surf)" }}
              >
                Quitar personalización
              </button>
            ) : (
              <span />
            )}
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-4 py-1.5 rounded-lg text-[12px] font-bold cursor-pointer border-0 transition-premium btn-hover disabled:opacity-50"
              style={{ background: "var(--brand)", color: "#fff" }}
            >
              {saving ? "Guardando..." : "Guardar"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// Modal de configuración de reglas heurísticas POR ENDPOINT (2026-08-16,
// ver PENDIENTES.md). Mismo patrón visual que RuleEditModal.tsx (portal
// a #app-shell, overlay, header eyebrow + título + X), pero lista las
// 12 reglas de una vez -- acá el analista ve, regla por regla, el valor
// global, si este endpoint tiene un override y el valor efectivo
// resultante, en vez de editar una regla sola a la vez.
export default function AgentRulesModal({ agentId, hostnameHint, onClose }: Props) {
  const [rules, setRules] = useState<AgentRuleItem[] | null>(null);
  const [hostname, setHostname] = useState(hostnameHint ?? "");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [entered, setEntered] = useState(false);

  const load = useCallback(() => {
    setLoadError(null);
    fetchAgentRules(agentId)
      .then((res) => {
        setRules(res.rules);
        setHostname(res.hostname);
      })
      .catch((e) => setLoadError(e instanceof Error ? e.message : "No se pudo cargar la configuración de reglas."));
  }, [agentId]);

  useEffect(() => {
    load();
    const raf = requestAnimationFrame(() => requestAnimationFrame(() => setEntered(true)));
    return () => cancelAnimationFrame(raf);
  }, [load]);

  function handleRuleUpdated(updated: AgentRuleItem) {
    setRules((prev) => (prev ? prev.map((r) => (r.id === updated.id ? updated : r)) : prev));
  }

  // Mismo motivo del portal que RuleEditModal.tsx: #app-shell trae las
  // variables de tema, document.body no.
  const portalTarget = document.getElementById("app-shell") ?? document.body;

  const customizedCount = rules ? rules.filter((r) => r.has_override).length : 0;

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
          className="w-full max-w-2xl rounded-2xl border flex flex-col shadow-2xl max-h-[88vh]"
          style={{ background: "var(--surf)", borderColor: "var(--line-soft)" }}
        >
          <div className="px-5 py-4 border-b flex items-start gap-4 shrink-0" style={{ borderColor: "var(--line-soft)" }}>
            <div className="min-w-0 flex-1">
              <div className="text-[11px] tracking-wider uppercase font-semibold" style={{ color: "var(--tx-mute)" }}>
                Configuración de reglas -- {hostname || `endpoint #${agentId}`}
              </div>
              <div className="text-[18px] font-bold mt-1 tracking-tight" style={{ color: "var(--tx)" }}>
                Reglas heurísticas de este endpoint
              </div>
              {rules && (
                <div className="text-[12px] mt-1" style={{ color: "var(--tx-mute)" }}>
                  {customizedCount === 0
                    ? "Sin personalizaciones -- este endpoint usa la configuración global en las 12 reglas."
                    : `${customizedCount} de ${rules.length} regla(s) con configuración personalizada.`}
                </div>
              )}
            </div>
            <button
              onClick={onClose}
              className="w-8 h-8 rounded-lg border grid place-items-center cursor-pointer transition-premium btn-hover shadow-sm"
              style={{ borderColor: "var(--line)", background: "var(--surf2)", color: "var(--tx-dim)" }}
            >
              <i className="ph-fill ph-x" style={{ fontSize: "15px" }} />
            </button>
          </div>

          <div className="px-5 py-4 flex flex-col gap-2.5 overflow-y-auto">
            {loadError && (
              <div className="rounded-[8px] px-3 py-2 text-[12px]" style={{ background: "var(--crit-soft)", color: "var(--crit)" }}>
                {loadError}
              </div>
            )}

            {!rules && !loadError && (
              <div className="text-[13px] py-6 text-center" style={{ color: "var(--tx-mute)" }}>
                Cargando reglas...
              </div>
            )}

            {rules &&
              rules.map((rule) => (
                <AgentRuleRow key={rule.id} rule={rule} agentId={agentId} onUpdated={handleRuleUpdated} />
              ))}
          </div>

          <div className="px-5 py-3.5 border-t flex justify-end shrink-0" style={{ borderColor: "var(--line-soft)" }}>
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-lg text-[13px] font-bold cursor-pointer transition-premium btn-hover shadow-sm"
              style={{ border: "1px solid var(--line)", color: "var(--tx-dim)", background: "var(--surf2)" }}
            >
              Cerrar
            </button>
          </div>
        </div>
      </div>
    </>,
    portalTarget
  );
}
