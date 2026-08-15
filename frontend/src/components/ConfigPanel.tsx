import { useState } from "react";
import { updateSetting } from "../api/client";

interface Props {
  agentStaleSeconds: number;
  onChanged: (value: number) => void;
}

export default function ConfigPanel({ agentStaleSeconds, onChanged }: Props) {
  const [input, setInput] = useState(String(agentStaleSeconds));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const dirty = input !== String(agentStaleSeconds);

  async function handleSave() {
    const parsed = Number(input);
    if (!Number.isInteger(parsed) || parsed <= 0) {
      setError("Tiene que ser un número entero mayor a 0.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await updateSetting("agent_stale_seconds", String(parsed));
      onChanged(parsed);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo guardar el parámetro.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section
      className="rounded-[10px] border p-4 flex flex-col gap-3.5"
      style={{ background: "var(--surf)", borderColor: "var(--line)", boxShadow: "var(--shadow)" }}
    >
      <h3 className="text-[13px] font-semibold" style={{ color: "var(--tx)" }}>Parámetros de conexión</h3>

      {error && (
        <div className="rounded-[8px] px-3 py-2 text-[12px]" style={{ background: "var(--crit-soft)", color: "var(--crit)" }}>
          {error}
        </div>
      )}
      {saved && (
        <div className="rounded-[8px] px-3 py-2 text-[12px]" style={{ background: "var(--ok-soft)", color: "var(--ok)" }}>
          Parámetro actualizado.
        </div>
      )}

      <div className="max-w-[420px]">
        <label className="text-[11.5px] font-semibold block mb-1.5" style={{ color: "var(--tx-mute)" }}>
          Tiempo sin heartbeat (segundos)
        </label>
        <div className="flex items-center gap-2">
          <input
            type="number"
            min={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            className="w-[120px] px-3 py-2 rounded-[8px] text-[13px] outline-none"
            style={{ background: "var(--surf2)", border: "1px solid var(--line)", color: "var(--tx)" }}
          />
          {dirty && (
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-3.5 py-2 rounded-[8px] text-[12px] font-semibold border-0 cursor-pointer disabled:opacity-50"
              style={{ background: "var(--brand)", color: "#fff" }}
            >
              {saving ? "Guardando..." : "Guardar"}
            </button>
          )}
        </div>
        <p className="text-[11px] mt-1.5 leading-relaxed" style={{ color: "var(--tx-mute)" }}>
          Tiempo sin heartbeat tras el cual un agente ONLINE pasa a "sin señal reciente" en vez de "en línea", en
          Endpoints, Dashboard e Incidentes. Cambio real: se guarda en <code>system_settings</code> y el servidor
          lo vuelve a leer en cada request.
        </p>
      </div>

      <div className="pt-3.5 border-t flex flex-col gap-3" style={{ borderColor: "var(--line-soft)" }}>
        <div>
          <div className="text-[11.5px] font-semibold" style={{ color: "var(--tx-mute)" }}>Intervalo de heartbeat</div>
          <div className="text-[12px] mt-1 leading-relaxed" style={{ color: "var(--tx-dim)" }}>
            No aplicable -- el agente manda heartbeat una sola vez al arrancar (no corre en segundo plano ni repite
            el envío), así que no existe un "intervalo" que configurar todavía.
          </div>
        </div>
        <div>
          <div className="text-[11.5px] font-semibold" style={{ color: "var(--tx-mute)" }}>Sincronización de reglas</div>
          <div className="text-[12px] mt-1 leading-relaxed" style={{ color: "var(--tx-dim)" }}>
            Real desde 2026-08-12: el agente pide <code>GET /agent/rule-policy</code> en cada ejecución y aplica
            el peso/umbral/ventana vigentes de cada regla activa (editables en Reglas Heurísticas). No hay un
            "intervalo" configurable porque el agente sigue sin bucle en segundo plano -- sincronizar significa
            "en el próximo arranque del agente", no en caliente sobre un proceso ya corriendo.
          </div>
        </div>
      </div>
    </section>
  );
}
