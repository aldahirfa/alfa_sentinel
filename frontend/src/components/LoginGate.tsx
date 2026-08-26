import { useState } from "react";
import { login } from "../api/client";

interface Props {
  onSuccess: () => void;
}

const NETWORK_LINES = [
  [45, 95, 155, 170], [155, 170, 105, 300], [155, 170, 320, 135],
  [320, 135, 425, 225], [105, 300, 245, 375], [245, 375, 425, 225],
  [245, 375, 180, 515], [180, 515, 325, 585], [325, 585, 425, 495],
  [425, 225, 462, 395], [462, 395, 425, 495],
];

const NETWORK_NODES = [
  [45, 95, 3], [155, 170, 4], [320, 135, 3], [105, 300, 3], [425, 225, 4],
  [245, 375, 4], [180, 515, 3], [462, 395, 3], [425, 495, 4], [325, 585, 3],
];

export default function LoginGate({ onSuccess }: Props) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showForgotNote, setShowForgotNote] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(username, password);
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo iniciar sesión");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex bg-[#070b13] text-[#0f1b2d]">
      <section
        className="hidden lg:flex flex-[1.08] relative flex-col justify-between px-14 xl:px-20 py-12 overflow-hidden text-[#f2f6fc] border-r border-[#17243a]"
        style={{ background: "linear-gradient(145deg, #070b13 0%, #0b1424 48%, #0d1b31 100%)" }}
      >
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background:
              "radial-gradient(circle at 24% 18%, rgba(77,141,255,.16), transparent 32rem), radial-gradient(circle at 86% 78%, rgba(56,189,248,.07), transparent 28rem)",
          }}
        />
        <div
          className="absolute inset-0 opacity-[.16] pointer-events-none"
          style={{
            backgroundImage: "linear-gradient(#223149 1px, transparent 1px), linear-gradient(90deg, #223149 1px, transparent 1px)",
            backgroundSize: "42px 42px",
            maskImage: "linear-gradient(to bottom, rgba(0,0,0,.5), transparent 90%)",
          }}
        />

        <svg className="absolute inset-0 opacity-[.28] w-full h-full pointer-events-none" viewBox="0 0 500 700" preserveAspectRatio="xMidYMid slice">
          <g stroke="#29405f" strokeWidth="1">
            {NETWORK_LINES.map(([x1, y1, x2, y2], i) => <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} />)}
          </g>
          <g fill="#4d8dff">
            {NETWORK_NODES.map(([cx, cy, r], i) => <circle key={i} cx={cx} cy={cy} r={r} />)}
          </g>
        </svg>

        <div className="relative z-10 flex items-center gap-3">
          <div
            className="w-10 h-10 rounded-xl border grid place-items-center"
            style={{ background: "rgba(77,141,255,.09)", borderColor: "rgba(77,141,255,.22)" }}
          >
            <img src="/static/logo-icon.png" alt="Sistema ALFA-Sentinel" className="w-[27px] h-auto" />
          </div>
          <div>
            <div className="text-[14px] font-bold tracking-[.02em]">ALFA-Sentinel</div>
            <div className="text-[9px] uppercase tracking-[.16em] mt-1 text-[#6f819a]">Consola central de seguridad</div>
          </div>
        </div>

        <div className="relative z-10 max-w-[620px]">
          <div className="flex items-center gap-7">
            <div className="relative w-[164px] h-[164px] shrink-0 hidden xl:flex items-center justify-center">
              <div className="absolute inset-0 rounded-full border border-[#29405f]" />
              <div className="absolute inset-[16%] rounded-full border border-[#223755]" />
              <div className="absolute inset-[32%] rounded-full border border-[#1c304c]" />
              <div className="absolute w-px h-full bg-gradient-to-b from-transparent via-[#4d8dff]/35 to-transparent rotate-[38deg]" />
              <div className="absolute h-px w-full bg-gradient-to-r from-transparent via-[#38bdf8]/25 to-transparent -rotate-[24deg]" />
              <div
                className="relative w-[72px] h-[72px] rounded-[20px] border grid place-items-center"
                style={{
                  background: "linear-gradient(145deg, #12213a, #0b1424)",
                  borderColor: "rgba(77,141,255,.32)",
                  boxShadow: "0 18px 46px rgba(0,0,0,.4), 0 0 35px rgba(77,141,255,.08)",
                }}
              >
                <img src="/static/logo-icon.png" alt="" className="w-[48px] h-auto" />
              </div>
            </div>

            <div>
              <div className="text-[11px] font-semibold text-[#7f95b2]">Sistema ALFA-Sentinel</div>
              <h1 className="m-0 mt-2 text-[34px] xl:text-[40px] leading-[1.04] font-bold tracking-[-.045em] text-[#f5f8fd]">
                Detección temprana de ransomware
              </h1>
              <p className="m-0 mt-4 max-w-[520px] text-[12px] xl:text-[13px] leading-[1.75] text-[#8fa0b7]">
                Supervisión centralizada de endpoints mediante archivos señuelo y análisis heurístico de procesos, con gestión de alertas, incidentes y acciones de respuesta.
              </p>
            </div>
          </div>
        </div>

        <div className="relative z-10 flex items-center justify-between gap-4 text-[9px] text-[#53677f]">
          <span>AGETIC · Estado Plurinacional de Bolivia</span>
          <span className="font-semibold tracking-[.12em] uppercase">Sistema ALFA-Sentinel</span>
        </div>
      </section>

      <section className="flex-1 flex items-center justify-center p-5 sm:p-10 relative overflow-hidden" style={{ background: "#f2f6fb" }}>
        <div className="absolute -top-32 -right-32 w-[420px] h-[420px] rounded-full pointer-events-none" style={{ background: "radial-gradient(circle, rgba(37,99,235,.10), transparent 68%)" }} />
        <div className="absolute -bottom-40 -left-40 w-[430px] h-[430px] rounded-full pointer-events-none" style={{ background: "radial-gradient(circle, rgba(8,124,173,.06), transparent 68%)" }} />

        <div
          className="relative w-full max-w-[420px] rounded-[24px] border bg-white px-7 sm:px-10 py-9 sm:py-10"
          style={{ borderColor: "#dfe8f3", boxShadow: "0 34px 76px -30px rgba(23,42,70,.28), 0 10px 28px rgba(23,42,70,.06)" }}
        >
          <div className="absolute top-0 left-10 right-10 h-[3px] rounded-b-full" style={{ background: "linear-gradient(90deg, #2563eb, #38bdf8)" }} />

          <div className="lg:hidden flex items-center gap-3 mb-8">
            <div className="w-10 h-10 rounded-xl border grid place-items-center" style={{ background: "#eef4ff", borderColor: "#d8e6ff" }}>
              <img src="/static/logo-icon.png" alt="Sistema ALFA-Sentinel" className="w-[27px] h-auto" />
            </div>
            <div>
              <div className="text-[13px] font-bold text-[#0f1b2d]">ALFA-Sentinel</div>
              <div className="text-[9px] mt-1 uppercase tracking-[.12em] text-[#7b8ba0]">Consola central de seguridad</div>
            </div>
          </div>

          <div className="text-[9px] font-bold tracking-[.14em] uppercase mb-3 text-[#2563eb]">Acceso al sistema</div>
          <h2 className="m-0 text-[26px] font-bold tracking-[-.035em] text-[#0f1b2d]">Iniciar sesión</h2>
          <p className="m-0 mt-2 text-[12px] leading-relaxed text-[#6d7d94]">Ingresa tus credenciales para acceder a la consola central.</p>

          {error && (
            <div className="mt-5 rounded-xl border px-3.5 py-3 text-[11px] flex items-start gap-2.5" style={{ background: "#fff2f4", borderColor: "#f5cbd2", color: "#c62f46" }}>
              <i className="ph-fill ph-warning-circle text-[15px] mt-px" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="mt-7">
            <div className="mb-4">
              <label className="block text-[10px] font-semibold text-[#52647c] mb-1.5">Usuario</label>
              <div className="relative">
                <i className="ph ph-user absolute left-3.5 top-1/2 -translate-y-1/2 text-[15px] text-[#7b8ba0]" />
                <input
                  type="text"
                  autoComplete="username"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Nombre de usuario"
                  className="w-full py-3 pl-10 pr-4 rounded-xl border text-[12px] text-[#0f1b2d] outline-none transition-all focus:border-[#2563eb] focus:shadow-[0_0_0_3px_rgba(37,99,235,.10)]"
                  style={{ background: "#f7faff", borderColor: "#d6e1ee" }}
                />
              </div>
            </div>

            <div>
              <label className="block text-[10px] font-semibold text-[#52647c] mb-1.5">Contraseña</label>
              <div className="relative">
                <i className="ph ph-lock-simple absolute left-3.5 top-1/2 -translate-y-1/2 text-[15px] text-[#7b8ba0]" />
                <input
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Contraseña"
                  className="w-full py-3 pl-10 pr-11 rounded-xl border text-[12px] text-[#0f1b2d] outline-none transition-all focus:border-[#2563eb] focus:shadow-[0_0_0_3px_rgba(37,99,235,.10)]"
                  style={{ background: "#f7faff", borderColor: "#d6e1ee" }}
                />
                <button
                  type="button"
                  aria-label="Mostrar u ocultar contraseña"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 border-0 bg-transparent cursor-pointer text-[#7b8ba0]"
                >
                  <i className={showPassword ? "ph ph-eye-slash" : "ph ph-eye"} style={{ fontSize: "16px" }} />
                </button>
              </div>
            </div>

            <div className="text-right mt-2.5">
              <button
                type="button"
                onClick={() => setShowForgotNote((v) => !v)}
                className="border-0 bg-transparent cursor-pointer text-[10px] font-semibold text-[#2563eb] p-0"
              >
                ¿Olvidaste tu contraseña?
              </button>
            </div>

            {showForgotNote && (
              <div className="mt-3 rounded-xl border px-3.5 py-3 text-[10px] leading-relaxed" style={{ background: "#f7faff", borderColor: "#dfe8f3", color: "#6d7d94" }}>
                Por seguridad, el restablecimiento de contraseña es gestionado por el administrador del sistema.
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-6 py-3 rounded-xl border-0 cursor-pointer text-white text-[11px] font-bold tracking-[.03em] disabled:opacity-60 transition-transform hover:-translate-y-px active:translate-y-0"
              style={{ background: "linear-gradient(115deg, #2563eb, #2f76f6)", boxShadow: "0 16px 28px -12px rgba(37,99,235,.48)" }}
            >
              <span className="inline-flex items-center justify-center gap-2">
                <i className={loading ? "ph ph-spinner" : "ph ph-sign-in"} style={{ fontSize: "14px" }} />
                {loading ? "Ingresando..." : "Ingresar a la consola"}
              </span>
            </button>
          </form>

          <div className="mt-8 pt-5 border-t text-center" style={{ borderColor: "#e7eef6" }}>
            <div className="text-[9.5px] font-semibold text-[#52647c]">Sistema ALFA-Sentinel · v1.0.0</div>
            <div className="text-[8.5px] text-[#8b98a9] mt-1">Plataforma de detección temprana y gestión de seguridad</div>
          </div>
        </div>
      </section>
    </div>
  );
}
