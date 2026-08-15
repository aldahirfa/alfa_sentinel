import { useState } from "react";
import type { HeuristicRule } from "../types/rules";
import { updateRule } from "../api/client";

interface Props {
  rule: HeuristicRule;
  onChanged: (updated: HeuristicRule) => void;
}

export default function RuleCard({ rule, onChanged }: Props) {
  const [weightInput, setWeightInput] = useState(String(rule.weight));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const weightDirty = weightInput !== String(rule.weight) && weightInput.trim() !== "";

  async function saveWeight() {
    const parsed = Number(weightInput);
    if (Number.isNaN(parsed) || parsed < 0) {
      setError("El peso tiene que ser un número mayor o igual a 0.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const res = await updateRule(rule.id, { weight: parsed });
      onChanged({ ...rule, weight: res.weight });
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo guardar el peso.");
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive() {
    setSaving(true);
    setError(null);
    try {
      const res = await updateRule(rule.id, { is_active: !rule.is_active });
      onChanged({ ...rule, is_active: res.is_active });
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo cambiar el estado.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className="rounded-[10px] border p-4"
      style={{
        background: "var(--surf)",
        borderColor: rule.is_active ? "var(--line)" : "var(--line-soft)",
        boxShadow: "var(--shadow)",
        opacity: rule.is_active ? 1 : 0.7,
      }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[14.5px] font-semibold" style={{ color: "var(--tx)" }}>{rule.label}</div>
          {rule.description && (
            <p className="text-[12px] mt-1 leading-relaxed" style={{ color: "var(--tx-mute)" }}>{rule.description}</p>
          )}
        </div>
        <button
          onClick={toggleActive}
          disabled={saving}
          className="shrink-0 flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10.5px] font-semibold cursor-pointer disabled:opacity-50"
          style={
            rule.is_active
              ? { background: "var(--ok-soft)", color: "var(--ok)", border: "1px solid var(--ok)" }
              : { background: "var(--surf2)", color: "var(--tx-mute)", border: "1px solid var(--line)" }
          }
        >
          <span className="w-1.5 h-1.5 rounded-full" style={{ background: rule.is_active ? "var(--ok)" : "var(--tx-mute)" }} />
          {rule.is_active ? "Activa" : "Inactiva"}
        </button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-3.5 pt-3.5 border-t" style={{ borderColor: "var(--line-soft)" }}>
        <div>
          <div className="text-[10px]" style={{ color: "var(--tx-mute)" }}>Tipo de evento</div>
          <div className="text-[12px] font-medium mt-1" style={{ color: "var(--tx-dim)" }}>{rule.event_type_label}</div>
        </div>
        <div>
          <div className="text-[10px]" style={{ color: "var(--tx-mute)" }}>Umbral / ventana</div>
          <div className="text-[12px] font-medium mt-1" style={{ color: "var(--tx-dim)" }}>
            {rule.threshold} en {rule.window_seconds}s
          </div>
        </div>
        <div>
          <div className="text-[10px]" style={{ color: "var(--tx-mute)" }}>Alertas (30 días)</div>
          <div className="text-[12px] font-medium mt-1" style={{ color: rule.alerts_30d > 0 ? "var(--warn)" : "var(--tx-dim)" }}>
            {rule.alerts_30d}
          </div>
        </div>
        <div>
          <div className="text-[10px]" style={{ color: "var(--tx-mute)" }}>Última activación</div>
          <div className="text-[12px] font-medium mt-1" style={{ color: "var(--tx-dim)" }}>
            {rule.last_triggered_at ?? "Nunca"}
          </div>
        </div>
      </div>

      <div className="flex items-end gap-2 mt-3.5 pt-3.5 border-t" style={{ borderColor: "var(--line-soft)" }}>
        <div className="flex-1 max-w-[140px]">
          <label className="text-[10px] block mb-1" style={{ color: "var(--tx-mute)" }}>Peso en el cálculo de riesgo</label>
          <input
            type="number"
            min={0}
            step={1}
            value={weightInput}
            onChange={(e) => setWeightInput(e.target.value)}
            className="w-full px-2.5 py-1.5 rounded-[8px] text-[13px] font-semibold tabular-nums outline-none"
            style={{ background: "var(--surf2)", border: "1px solid var(--line)", color: "var(--tx)" }}
          />
        </div>
        {weightDirty && (
          <button
            onClick={saveWeight}
            disabled={saving}
            className="px-3 py-1.5 rounded-[8px] text-[12px] font-semibold cursor-pointer border-0 disabled:opacity-50"
            style={{ background: "var(--brand)", color: "#fff" }}
          >
            Guardar
          </button>
        )}
        {error && <span className="text-[11px] ml-1" style={{ color: "var(--crit)" }}>{error}</span>}
      </div>
    </div>
  );
}
