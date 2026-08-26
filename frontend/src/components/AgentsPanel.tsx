import { useState } from "react";
import { createEnrollmentToken } from "../api/client";
import type { EnrollmentTokenResult } from "../types/admin";

interface Props {
  isAdmin: boolean;
}

export default function AgentsPanel({ isAdmin }: Props) {
  const [token, setToken] = useState<EnrollmentTokenResult | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function handleGenerate() {
    setSaving(true);
    setError(null);
    setCopied(false);
    try {
      const result = await createEnrollmentToken();
      setToken(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo generar el token.");
    } finally {
      setSaving(false);
    }
  }

  function handleCopy() {
    if (!token) return;
    navigator.clipboard?.writeText(token.token).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 3000);
    });
  }

  return (
    <section className="soc-panel rounded-2xl overflow-hidden">
      <div className="px-5 py-4 border-b flex items-center gap-3" style={{ borderColor: "var(--line-soft)", background: "linear-gradient(90deg, var(--surf), var(--surf2))" }}>
        <div className="w-9 h-9 rounded-xl grid place-items-center" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
          <i className="ph ph-desktop-tower" style={{ fontSize: "17px" }} />
        </div>
        <div>
          <div className="text-[9px] font-bold tracking-[.15em] uppercase" style={{ color: "var(--brand)" }}>Registro controlado</div>
          <div className="text-[13px] font-semibold mt-0.5" style={{ color: "var(--tx)" }}>Enrolamiento de agentes</div>
        </div>
      </div>

      <div className="p-5 grid grid-cols-1 xl:grid-cols-[1fr_380px] gap-5">
        <div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {[
              ["01", "Generar token", "Se crea una credencial temporal de un solo uso."],
              ["02", "Registrar endpoint", "El instalador usa el token para solicitar el enrolamiento."],
              ["03", "Emitir credencial", "El servidor entrega la credencial individual permanente del agente."],
            ].map(([step, title, text]) => (
              <div key={step} className="rounded-xl border p-3.5" style={{ background: "var(--surf2)", borderColor: "var(--line-soft)" }}>
                <div className="mono-data text-[9px] font-bold" style={{ color: "var(--brand)" }}>{step}</div>
                <div className="text-[10.5px] font-semibold mt-1.5" style={{ color: "var(--tx)" }}>{title}</div>
                <div className="text-[9.5px] leading-relaxed mt-1.5" style={{ color: "var(--tx-mute)" }}>{text}</div>
              </div>
            ))}
          </div>

          <div className="mt-4 text-[10px] leading-relaxed" style={{ color: "var(--tx-mute)" }}>
            El token es válido durante 15 minutos y se utiliza únicamente para el registro inicial. La credencial persistente del agente se emite después de validar el enrolamiento.
          </div>

          {!isAdmin ? (
            <div className="mt-4 rounded-xl px-3.5 py-3 text-[10px] flex items-start gap-2.5" style={{ background: "var(--info-fill)", color: "var(--tx-dim)", border: "1px solid var(--info-soft)" }}>
              <i className="ph ph-info mt-0.5" style={{ color: "var(--info)" }} />
              <span>La generación de tokens requiere permisos administrativos.</span>
            </div>
          ) : (
            <button onClick={handleGenerate} disabled={saving} className="mt-4 inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-[11px] font-bold border-0 cursor-pointer disabled:opacity-50 transition-premium btn-hover" style={{ background: "var(--brand)", color: "#fff", boxShadow: "0 8px 24px var(--brand-glow)" }}>
              <i className={saving ? "ph ph-spinner" : "ph ph-key"} style={{ fontSize: "14px" }} />
              {saving ? "Generando token..." : "Generar token de enrolamiento"}
            </button>
          )}

          {error && <div className="mt-3 rounded-xl px-3.5 py-3 text-[10px]" style={{ background: "var(--crit-soft)", color: "var(--crit)" }}>{error}</div>}
        </div>

        <div className="rounded-2xl border p-4 min-h-[210px]" style={{ background: "color-mix(in srgb, var(--surf2) 82%, transparent)", borderColor: "var(--line-soft)" }}>
          <div className="text-[9px] font-bold tracking-[.13em] uppercase" style={{ color: "var(--tx-mute)" }}>Credencial temporal</div>
          {!token ? (
            <div className="h-full min-h-[165px] grid place-items-center text-center">
              <div>
                <div className="w-12 h-12 rounded-2xl mx-auto grid place-items-center" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}><i className="ph ph-key" style={{ fontSize: "22px" }} /></div>
                <div className="text-[10px] mt-3" style={{ color: "var(--tx-mute)" }}>Genera un token para mostrarlo aquí.</div>
              </div>
            </div>
          ) : (
            <div className="mt-4">
              <div className="text-[9.5px]" style={{ color: "var(--tx-mute)" }}>Se muestra una sola vez. Cópialo antes de abandonar esta vista.</div>
              <code className="mono-data block mt-3 p-3 rounded-xl text-[10.5px] overflow-x-auto whitespace-nowrap" style={{ background: "var(--surf3)", color: "var(--tx)", border: "1px solid var(--line-soft)" }}>{token.token}</code>
              <button onClick={handleCopy} className="mt-3 w-full inline-flex items-center justify-center gap-2 px-3 py-2 rounded-xl border cursor-pointer transition-premium btn-hover" style={{ background: copied ? "var(--ok-soft)" : "var(--brand-fill)", borderColor: copied ? "var(--ok-soft)" : "var(--brand-soft)", color: copied ? "var(--ok)" : "var(--brand)" }}>
                <i className={copied ? "ph ph-check" : "ph ph-copy"} />
                <span className="text-[10px] font-semibold">{copied ? "Token copiado" : "Copiar token"}</span>
              </button>
              <div className="text-[9px] mt-3" style={{ color: "var(--tx-mute)" }}>Expira: {new Date(token.expires_at).toLocaleString("es-BO")}</div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
