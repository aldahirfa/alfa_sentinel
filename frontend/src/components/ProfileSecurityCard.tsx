import { useState } from "react";
import { changePassword } from "../api/client";

const fieldStyle: React.CSSProperties = {
  background: "var(--surf2)",
  border: "1px solid var(--line)",
  color: "var(--tx)",
};

export default function ProfileSecurityCard() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNext, setShowNext] = useState(false);

  const dirty = current.length > 0 || next.length > 0 || confirm.length > 0;
  const strongEnough = next.length >= 8;
  const matches = next.length > 0 && next === confirm;

  async function handleSave() {
    setError(null);
    if (next.length < 8) {
      setError("La nueva contraseña debe tener al menos 8 caracteres.");
      return;
    }
    if (next !== confirm) {
      setError("La nueva contraseña y su confirmación no coinciden.");
      return;
    }
    setSaving(true);
    try {
      await changePassword({ current_password: current, new_password: next });
      setCurrent("");
      setNext("");
      setConfirm("");
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo cambiar la contraseña.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="soc-panel rounded-2xl overflow-hidden">
      <div className="px-5 py-4 border-b flex items-center gap-3" style={{ borderColor: "var(--line-soft)", background: "linear-gradient(90deg, var(--surf), var(--surf2))" }}>
        <div className="w-11 h-11 rounded-2xl grid place-items-center" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
          <i className="ph ph-lock-key" style={{ fontSize: "20px" }} />
        </div>
        <div>
          <div className="text-[9px] font-bold tracking-[.14em] uppercase" style={{ color: "var(--brand)" }}>Seguridad de la cuenta</div>
          <div className="text-[13px] font-semibold mt-0.5" style={{ color: "var(--tx)" }}>Credenciales de acceso</div>
          <div className="text-[9.5px] mt-0.5" style={{ color: "var(--tx-mute)" }}>Actualiza tu contraseña de acceso a la consola.</div>
        </div>
      </div>

      <div className="p-5">
        {error && <div className="rounded-xl px-3 py-2.5 text-[10px] mb-4" style={{ background: "var(--crit-soft)", color: "var(--crit)" }}>{error}</div>}
        {saved && <div className="rounded-xl px-3 py-2.5 text-[10px] mb-4" style={{ background: "var(--ok-soft)", color: "var(--ok)" }}>Contraseña actualizada correctamente.</div>}

        <div className="rounded-xl border p-3.5 mb-4" style={{ background: "var(--surf2)", borderColor: "var(--line-soft)" }}>
          <div className="flex gap-3 items-start">
            <div className="w-8 h-8 rounded-lg grid place-items-center shrink-0" style={{ background: "var(--info-soft)", color: "var(--info)" }}>
              <i className="ph ph-shield-check" style={{ fontSize: "14px" }} />
            </div>
            <div>
              <div className="text-[10px] font-semibold" style={{ color: "var(--tx)" }}>Protege tu acceso</div>
              <div className="text-[9.5px] leading-relaxed mt-1" style={{ color: "var(--tx-mute)" }}>Utiliza una contraseña distinta a la de otros servicios y evita compartir tus credenciales de consola.</div>
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-3">
          <div>
            <label className="text-[9.5px] font-semibold block mb-1.5" style={{ color: "var(--tx-mute)" }}>Contraseña actual</label>
            <div className="relative">
              <i className="ph ph-key absolute left-3 top-1/2 -translate-y-1/2" style={{ fontSize: "14px", color: "var(--tx-mute)" }} />
              <input type={showCurrent ? "text" : "password"} value={current} onChange={(e) => setCurrent(e.target.value)} className="w-full pl-9 pr-10 py-2.5 rounded-xl text-[11px] outline-none" style={fieldStyle} />
              <button type="button" onClick={() => setShowCurrent((v) => !v)} className="absolute right-3 top-1/2 -translate-y-1/2 border-0 bg-transparent cursor-pointer" style={{ color: "var(--tx-mute)" }} aria-label="Mostrar u ocultar contraseña actual">
                <i className={showCurrent ? "ph ph-eye-slash" : "ph ph-eye"} />
              </button>
            </div>
          </div>

          <div>
            <label className="text-[9.5px] font-semibold block mb-1.5" style={{ color: "var(--tx-mute)" }}>Nueva contraseña</label>
            <div className="relative">
              <i className="ph ph-lock-simple absolute left-3 top-1/2 -translate-y-1/2" style={{ fontSize: "14px", color: "var(--tx-mute)" }} />
              <input type={showNext ? "text" : "password"} value={next} onChange={(e) => setNext(e.target.value)} className="w-full pl-9 pr-10 py-2.5 rounded-xl text-[11px] outline-none" style={fieldStyle} />
              <button type="button" onClick={() => setShowNext((v) => !v)} className="absolute right-3 top-1/2 -translate-y-1/2 border-0 bg-transparent cursor-pointer" style={{ color: "var(--tx-mute)" }} aria-label="Mostrar u ocultar nueva contraseña">
                <i className={showNext ? "ph ph-eye-slash" : "ph ph-eye"} />
              </button>
            </div>
            <div className="flex items-center gap-2 mt-2 text-[9px]" style={{ color: strongEnough ? "var(--ok)" : "var(--tx-mute)" }}>
              <i className={strongEnough ? "ph-fill ph-check-circle" : "ph ph-circle"} />
              Mínimo 8 caracteres
            </div>
          </div>

          <div>
            <label className="text-[9.5px] font-semibold block mb-1.5" style={{ color: "var(--tx-mute)" }}>Confirmar nueva contraseña</label>
            <div className="relative">
              <i className="ph ph-check-circle absolute left-3 top-1/2 -translate-y-1/2" style={{ fontSize: "14px", color: "var(--tx-mute)" }} />
              <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} className="w-full pl-9 pr-3 py-2.5 rounded-xl text-[11px] outline-none" style={fieldStyle} />
            </div>
            {confirm.length > 0 && (
              <div className="flex items-center gap-2 mt-2 text-[9px]" style={{ color: matches ? "var(--ok)" : "var(--crit)" }}>
                <i className={matches ? "ph-fill ph-check-circle" : "ph-fill ph-x-circle"} />
                {matches ? "Las contraseñas coinciden" : "Las contraseñas no coinciden"}
              </div>
            )}
          </div>

          <div className="min-h-[34px]">
            {dirty && (
              <button onClick={handleSave} disabled={saving} className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-[10px] font-semibold border-0 cursor-pointer disabled:opacity-50 transition-premium btn-hover" style={{ background: "var(--brand)", color: "#fff", boxShadow: "var(--shadow-blue)" }}>
                <i className={saving ? "ph ph-spinner" : "ph ph-lock-key"} />
                {saving ? "Actualizando..." : "Cambiar contraseña"}
              </button>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
