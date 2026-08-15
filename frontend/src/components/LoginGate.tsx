import { useState } from "react";
import { User, Lock, Eye } from "lucide-react";
import { login } from "../api/client";

// Réplica del login real (server/templates/login.html): misma
// estructura de dos paneles, mismo logo (/static/logo-icon.png, vía
// el proxy de Vite -- no se duplica el archivo), mismo texto y mismos
// campos. Convertido a componentes/Tailwind, no reinventado.

interface Props {
  onSuccess: () => void;
}

const NETWORK_LINES = [
  [60, 110, 175, 185],
  [175, 185, 130, 315],
  [175, 185, 335, 150],
  [335, 150, 430, 240],
  [130, 315, 250, 390],
  [250, 390, 430, 240],
  [250, 390, 190, 530],
  [190, 530, 330, 600],
  [330, 600, 420, 510],
  [430, 240, 460, 410],
  [460, 410, 420, 510],
];

const NETWORK_NODES = [
  [60, 110, 3],
  [175, 185, 4],
  [335, 150, 3],
  [130, 315, 3],
  [430, 240, 4],
  [250, 390, 4],
  [190, 530, 3],
  [460, 410, 3],
  [420, 510, 4],
  [330, 600, 3],
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
    <div className="min-h-screen flex text-[#131a30]">
      {/* Panel izquierdo -- réplica de .brand-panel */}
      <div
        className="hidden md:flex flex-[1.2] relative flex-col justify-between px-16 py-14 overflow-hidden text-[#eef1f8]"
        style={{
          background:
            "radial-gradient(circle at 30% 15%, rgba(91,143,224,0.22), transparent 45%), radial-gradient(circle at 80% 85%, rgba(90,60,200,0.28), transparent 50%), linear-gradient(160deg, #060d1f 0%, #0c1a3a 45%, #241a5e 100%)",
        }}
      >
        <svg
          className="absolute inset-0 opacity-40 w-full h-full"
          viewBox="0 0 500 700"
          preserveAspectRatio="xMidYMid slice"
        >
          <g stroke="#3a4f7d" strokeWidth="1">
            {NETWORK_LINES.map(([x1, y1, x2, y2], i) => (
              <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} />
            ))}
          </g>
          <line
            className="stroke-[#5b8fe0] animate-travel"
            strokeWidth="1.4"
            strokeDasharray="6 220"
            x1={175} y1={185} x2={335} y2={150}
          />
          <line
            className="stroke-[#5b8fe0] animate-travel"
            strokeWidth="1.4"
            strokeDasharray="6 220"
            style={{ animationDelay: "2.2s" }}
            x1={250} y1={390} x2={430} y2={240}
          />
          <g fill="#6a8fe0">
            {NETWORK_NODES.map(([cx, cy, r], i) => (
              <circle key={i} cx={cx} cy={cy} r={r} />
            ))}
          </g>
        </svg>

        <div className="relative z-10 flex items-center gap-2.5">
          <img src="/static/logo-icon.png" alt="" width={26} className="h-auto" />
          <span className="text-[15px] font-semibold tracking-wide text-[#cfd9f0]">
            ALFA-SENTINEL
          </span>
        </div>

        <div>
          <div className="relative z-10 mx-auto w-[220px] h-[220px] flex items-center justify-center">
            <div className="absolute inset-0 rounded-full border border-[#5b8fe0]/35" />
            <div className="absolute inset-[14%] rounded-full border border-[#5b8fe0]/35" />
            <div className="absolute inset-[27%] rounded-full border border-[#5b8fe0]/35" />
            <div className="absolute inset-0 rounded-full border-[1.5px] border-[#5b8fe0] animate-pulse-ring" />
            <div
              className="absolute inset-0 rounded-full border-[1.5px] border-[#5b8fe0] animate-pulse-ring"
              style={{ animationDelay: "1.6s" }}
            />
            <div
              className="relative z-10 w-[84px] h-[84px] rounded-[22px] flex items-center justify-center border border-[#5b8fe0]/50"
              style={{
                background: "linear-gradient(150deg, #16234a, #0c1530)",
                boxShadow: "0 0 0 1px rgba(91,143,224,0.15), 0 20px 40px -10px rgba(0,0,0,0.6)",
              }}
            >
              <img
                src="/static/logo-icon.png"
                alt="ALFA-Sentinel"
                className="w-[58px] h-auto"
                style={{ filter: "drop-shadow(0 0 10px rgba(91,143,224,0.5))" }}
              />
            </div>
          </div>

          <div className="relative z-10 text-center mt-7">
            <p className="text-[1.7rem] font-bold tracking-tight bg-gradient-to-r from-[#eef1f8] to-[#a9c1f0] bg-clip-text text-transparent mb-2.5">
              ALFA-Sentinel
            </p>
            <p className="text-[1.02rem] font-medium text-[#c4cfe8] max-w-[380px] mx-auto mb-3.5 leading-snug">
              Plataforma de Detección Temprana y Gestión de Seguridad
            </p>
            <p className="text-[0.85rem] text-[#8493b8] max-w-[360px] mx-auto leading-relaxed">
              Monitoreo continuo de endpoints, análisis de comportamiento y
              detección temprana de actividades potencialmente maliciosas.
            </p>
          </div>
        </div>

        <div className="relative z-10 flex items-center justify-center gap-2.5 text-[0.7rem] tracking-[0.18em] text-[#6577a3] font-semibold">
          <span>SECURITY</span>
          <span className="w-1 h-1 rounded-full bg-[#3d4d78]" />
          <span>MONITORING</span>
          <span className="w-1 h-1 rounded-full bg-[#3d4d78]" />
          <span>RESPONSE</span>
        </div>
      </div>

      {/* Panel derecho -- réplica de .form-panel / .form-card */}
      <div
        className="flex-1 flex items-center justify-center p-10"
        style={{
          background:
            "radial-gradient(circle at 15% 10%, rgba(48,89,214,0.06), transparent 40%), radial-gradient(circle at 90% 90%, rgba(36,26,94,0.05), transparent 45%), #eef1f8",
        }}
      >
        <div
          className="relative w-full max-w-[380px] bg-white rounded-[20px] px-10 py-11 border border-white/60"
          style={{ boxShadow: "0 40px 70px -24px rgba(19,26,48,0.22), 0 14px 28px -18px rgba(19,26,48,0.18)" }}
        >
          <div
            className="absolute top-0 left-10 right-10 h-[3px] rounded-b"
            style={{ background: "linear-gradient(90deg, #5b8fe0, #3059d6, #241a5e)" }}
          />

          <div className="flex md:hidden items-center gap-2 mb-7">
            <img src="/static/logo-icon.png" alt="" width={30} className="h-auto" />
            <span className="font-bold text-[#131a30]">ALFA-Sentinel</span>
          </div>

          <h2 className="text-[1.55rem] font-bold text-[#131a30] mb-1.5">Bienvenido</h2>
          <p className="text-[0.9rem] text-[#6b7690] mb-1">Inicia sesión en ALFA-Sentinel</p>
          <p className="text-[0.83rem] text-[#6b7690] mb-7 leading-relaxed">
            Accede a la consola de gestión y supervisión de seguridad.
          </p>

          {error && (
            <div className="bg-[#fdecec] border border-[#f3c6c6] text-[#c0392b] px-3.5 py-2.5 rounded-md text-[0.8rem] mb-4">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <div className="mb-4">
              <label className="block text-[0.76rem] font-semibold text-[#3a4560] mb-1.5">
                Usuario
              </label>
              <div className="relative flex items-center">
                <User size={16} className="absolute left-3.5 text-[#6b7690] pointer-events-none" />
                <input
                  type="text"
                  autoComplete="username"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full py-[0.68rem] pl-10 pr-4 rounded-[9px] border-[1.5px] border-[#e6e9f2] bg-[#fbfcfe] text-[0.92rem] text-[#131a30] outline-none focus:border-[#5b8fe0] focus:bg-white focus:shadow-[0_0_0_4px_rgba(48,89,214,0.1)] transition-colors"
                />
              </div>
            </div>

            <div className="mb-1">
              <label className="block text-[0.76rem] font-semibold text-[#3a4560] mb-1.5">
                Contraseña
              </label>
              <div className="relative flex items-center">
                <Lock size={16} className="absolute left-3.5 text-[#6b7690] pointer-events-none" />
                <input
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full py-[0.68rem] pl-10 pr-10 rounded-[9px] border-[1.5px] border-[#e6e9f2] bg-[#fbfcfe] text-[0.92rem] text-[#131a30] outline-none focus:border-[#5b8fe0] focus:bg-white focus:shadow-[0_0_0_4px_rgba(48,89,214,0.1)] transition-colors"
                />
                <button
                  type="button"
                  aria-label="Mostrar contraseña"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 text-[#6b7690]"
                >
                  <Eye size={17} />
                </button>
              </div>
            </div>

            <div className="text-right mt-1 mb-3">
              <a
                href="#"
                onClick={(e) => {
                  e.preventDefault();
                  setShowForgotNote((v) => !v);
                }}
                className="text-[0.79rem] font-medium text-[#3059d6] hover:underline"
              >
                ¿Olvidaste tu contraseña?
              </a>
            </div>

            {showForgotNote && (
              <div className="text-[0.77rem] text-[#6b7690] bg-[#eef2f9] border border-[#e6e9f2] px-3 py-2 rounded-md mb-4">
                Por seguridad, el restablecimiento de contraseña lo gestiona tu administrador del sistema.
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-[0.82rem] rounded-[10px] text-white text-[0.9rem] font-bold tracking-wide disabled:opacity-60 transition-transform hover:-translate-y-px active:translate-y-px"
              style={{
                background: "linear-gradient(120deg, #5b8fe0, #3059d6)",
                boxShadow: "0 14px 24px -10px rgba(48,89,214,0.55)",
              }}
            >
              {loading ? "INGRESANDO..." : "INICIAR SESIÓN"}
            </button>
          </form>

          <div className="mt-9 text-center">
            <div className="text-[0.76rem] font-semibold text-[#3a4560]">ALFA-Sentinel v1.0.0</div>
            <div className="text-[0.71rem] text-[#6b7690] mt-0.5">
              © 2026 — Plataforma de Gestión de Seguridad
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
