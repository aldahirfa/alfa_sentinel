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

  const dirty = current.length > 0 || next.length > 0 || confirm.length > 0;

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
    <section
      className="rounded-[10px] border p-4 flex flex-col gap-3.5"
      style={{ background: "var(--surf)", borderColor: "var(--line)", boxShadow: "var(--shadow)" }}
    >
      <h3 className="text-[13px] font-semibold" style={{ color: "var(--tx)" }}>Seguridad</h3>

      {error && (
        <div className="rounded-[8px] px-3 py-2 text-[12px]" style={{ background: "var(--crit-soft)", color: "var(--crit)" }}>
          {error}
        </div>
      )}
      {saved && (
        <div className="rounded-[8px] px-3 py-2 text-[12px]" style={{ background: "var(--ok-soft)", color: "var(--ok)" }}>
          Contraseña actualizada.
        </div>
      )}

      <div className="flex flex-col gap-3 max-w-[420px]">
        <div>
          <label className="text-[11.5px] font-semibold block mb-1.5" style={{ color: "var(--tx-mute)" }}>
            Contraseña actual
          </label>
          <input
            type="password"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            className="w-full px-3 py-2 rounded-[8px] text-[13px] outline-none"
            style={fieldStyle}
          />
        </div>

        <div>
          <label className="text-[11.5px] font-semibold block mb-1.5" style={{ color: "var(--tx-mute)" }}>
            Nueva contraseña (mínimo 8 caracteres)
          </label>
          <input
            type="password"
            value={next}
            onChange={(e) => setNext(e.target.value)}
            className="w-full px-3 py-2 rounded-[8px] text-[13px] outline-none"
            style={fieldStyle}
          />
        </div>

        <div>
          <label className="text-[11.5px] font-semibold block mb-1.5" style={{ color: "var(--tx-mute)" }}>
            Confirmar nueva contraseña
          </label>
          <input
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            className="w-full px-3 py-2 rounded-[8px] text-[13px] outline-none"
            style={fieldStyle}
          />
        </div>

        {dirty && (
          <button
            onClick={handleSave}
            disabled={saving}
            className="self-start px-3.5 py-2 rounded-[8px] text-[12px] font-semibold border-0 cursor-pointer disabled:opacity-50"
            style={{ background: "var(--brand)", color: "#fff" }}
          >
            {saving ? "Guardando..." : "Cambiar contraseña"}
          </button>
        )}
      </div>
    </section>
  );
}
