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
    <section className="soc-panel rounded-2xl overflow-hidden">
      <div className="px-5 py-4 border-b flex items-center gap-3" style={{ borderColor: "var(--line-soft)", background: "linear-gradient(90deg, var(--surf), var(--surf2))" }}>
        <div className="w-9 h-9 rounded-xl grid place-items-center" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}><i className="ph ph-sliders-horizontal" style={{ fontSize: "17px" }} /></div>
        <div><div className="text-[9px] font-bold tracking-[.15em] uppercase" style={{ color: "var(--brand)" }}>Parámetros operativos</div><div className="text-[13px] font-semibold mt-0.5" style={{ color: "var(--tx)" }}>Estado y sincronización de agentes</div></div>
      </div>

      <div className="p-5 grid grid-cols-1 xl:grid-cols-[440px_1fr] gap-5">
        <div className="rounded-2xl border p-4" style={{ background: "var(--surf2)", borderColor: "var(--line-soft)" }}>
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl grid place-items-center shrink-0" style={{ background: "var(--info-soft)", color: "var(--info)" }}><i className="ph ph-heartbeat" style={{ fontSize: "18px" }} /></div>
            <div><div className="text-[10.5px] font-semibold" style={{ color: "var(--tx)" }}>Umbral de señal reciente</div><div className="text-[9.5px] mt-1.5 leading-relaxed" style={{ color: "var(--tx-mute)" }}>Tiempo sin heartbeat tras el cual un agente deja de considerarse con señal reciente en la consola.</div></div>
          </div>

          <div className="mt-4 flex items-end gap-3">
            <div><label className="text-[9px] font-semibold block mb-1.5" style={{ color: "var(--tx-mute)" }}>Segundos</label><input type="number" min={1} value={input} onChange={(e) => setInput(e.target.value)} className="w-[130px] px-3 py-2.5 rounded-xl text-[12px] outline-none" style={{ background: "var(--surf)", border: "1px solid var(--line-soft)", color: "var(--tx)" }} /></div>
            <div className="text-[9.5px] pb-2.5" style={{ color: "var(--tx-mute)" }}>Valor actual: <b style={{ color: "var(--tx-dim)" }}>{agentStaleSeconds}s</b></div>
          </div>

          {(error || saved) && <div className="mt-3 rounded-xl px-3 py-2.5 text-[9.5px]" style={error ? { background: "var(--crit-soft)", color: "var(--crit)" } : { background: "var(--ok-soft)", color: "var(--ok)" }}>{error ?? "Parámetro actualizado correctamente."}</div>}

          <div className="mt-4 flex justify-end">
            <button onClick={handleSave} disabled={!dirty || saving} className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-[10px] font-semibold border-0 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed transition-premium btn-hover" style={{ background: "var(--brand)", color: "#fff" }}><i className={saving ? "ph ph-spinner" : "ph ph-floppy-disk"} />{saving ? "Guardando..." : "Guardar cambios"}</button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="rounded-2xl border p-4" style={{ background: "var(--surf2)", borderColor: "var(--line-soft)" }}>
            <div className="flex items-center gap-2.5"><div className="w-8 h-8 rounded-xl grid place-items-center" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}><i className="ph ph-clock" /></div><div className="text-[10.5px] font-semibold" style={{ color: "var(--tx)" }}>Intervalo de heartbeat</div></div>
            <div className="mt-3 inline-flex px-2 py-1 rounded-lg text-[9px]" style={{ background: "var(--surf3)", color: "var(--tx-mute)" }}>No configurable actualmente</div>
            <p className="text-[9.5px] mt-3 leading-relaxed" style={{ color: "var(--tx-mute)" }}>El agente envía heartbeat al iniciar; todavía no existe un ciclo periódico en segundo plano sobre el cual definir un intervalo.</p>
          </div>

          <div className="rounded-2xl border p-4" style={{ background: "var(--surf2)", borderColor: "var(--line-soft)" }}>
            <div className="flex items-center gap-2.5"><div className="w-8 h-8 rounded-xl grid place-items-center" style={{ background: "var(--ok-soft)", color: "var(--ok)" }}><i className="ph ph-arrows-clockwise" /></div><div className="text-[10.5px] font-semibold" style={{ color: "var(--tx)" }}>Sincronización de reglas</div></div>
            <div className="mt-3 inline-flex px-2 py-1 rounded-lg text-[9px]" style={{ background: "var(--ok-soft)", color: "var(--ok)" }}>Activa</div>
            <p className="text-[9.5px] mt-3 leading-relaxed" style={{ color: "var(--tx-mute)" }}>El agente consulta la política efectiva al iniciar y aplica los parámetros vigentes de cada regla activa. Los cambios se reflejan en el próximo arranque.</p>
          </div>
        </div>
      </div>
    </section>
  );
}
