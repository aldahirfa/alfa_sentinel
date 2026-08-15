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
    <section
      className="rounded-[10px] border p-4 flex flex-col gap-3.5"
      style={{ background: "var(--surf)", borderColor: "var(--line)", boxShadow: "var(--shadow)" }}
    >
      <div>
        <h3 className="text-[13px] font-semibold" style={{ color: "var(--tx)" }}>Enrolamiento de agentes</h3>
        <p className="text-[12px] mt-1.5 leading-relaxed" style={{ color: "var(--tx-mute)" }}>
          Genera un token de un solo uso, válido por 15 minutos, para instalar el agente en un endpoint nuevo.
          El instalador lo usa contra <code>POST /enrollment</code> para registrarse y obtener su credencial permanente.
        </p>
      </div>

      {!isAdmin ? (
        <p className="text-[11.5px]" style={{ color: "var(--tx-mute)" }}>
          Solo el rol <code>admin</code> puede generar tokens de enrolamiento.
        </p>
      ) : (
        <>
          {error && (
            <div className="rounded-[8px] px-3 py-2 text-[12px]" style={{ background: "var(--crit-soft)", color: "var(--crit)" }}>
              {error}
            </div>
          )}

          <button
            onClick={handleGenerate}
            disabled={saving}
            className="self-start flex items-center gap-2 px-4 py-2 rounded-[9px] text-[12.5px] font-semibold border-0 cursor-pointer disabled:opacity-50"
            style={{ background: "var(--brand)", color: "#fff" }}
          >
            <i className="ph ph-key" style={{ fontSize: "15px" }} />
            {saving ? "Generando..." : "Generar token de enrolamiento"}
          </button>

          {token && (
            <div className="rounded-[9px] p-3.5" style={{ background: "var(--surf2)", border: "1px solid var(--line)" }}>
              <div className="text-[11px] font-semibold mb-1.5" style={{ color: "var(--tx-mute)" }}>
                Token (se muestra una sola vez -- copialo ahora)
              </div>
              <div className="flex items-center gap-2">
                <code
                  className="flex-1 text-[11.5px] px-2.5 py-2 rounded-[7px] overflow-x-auto whitespace-nowrap"
                  style={{ background: "var(--surf3)", color: "var(--tx)" }}
                >
                  {token.token}
                </code>
                <button
                  onClick={handleCopy}
                  className="shrink-0 px-2.5 py-2 rounded-[7px] text-[11.5px] font-medium cursor-pointer"
                  style={{ border: "1px solid var(--line)", color: "var(--tx-dim)", background: "var(--surf)" }}
                >
                  {copied ? "Copiado" : "Copiar"}
                </button>
              </div>
              <div className="text-[10.5px] mt-2" style={{ color: "var(--tx-mute)" }}>
                Expira: {new Date(token.expires_at).toLocaleString("es-BO")}
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}
