import { useEffect, useState } from "react";
import ProfileInfoCard from "../components/ProfileInfoCard";
import ProfileSecurityCard from "../components/ProfileSecurityCard";
import { fetchProfile } from "../api/client";
import type { ProfileResponse } from "../types/perfil";

interface Props {
  roleLabel: string;
}

export default function PerfilPage({ roleLabel }: Props) {
  const [data, setData] = useState<ProfileResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  function load() {
    setLoading(true);
    fetchProfile()
      .then((res) => {
        setData(res);
        setError(null);
      })
      .catch(() => setError("No se pudo cargar el perfil."))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  return (
    <main className="soc-page px-[22px] pt-[18px] pb-10">
      <div className="max-w-[980px] mx-auto flex flex-col gap-4">
        <section className="soc-panel-strong rounded-[22px] p-5 relative overflow-hidden">
          <div
            className="absolute -right-14 -top-20 w-[260px] h-[260px] rounded-full pointer-events-none"
            style={{ background: "radial-gradient(circle, var(--brand-glow), transparent 70%)", opacity: .5 }}
          />
          <div className="relative z-[1] flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl grid place-items-center border" style={{ background: "var(--brand-soft)", borderColor: "var(--brand-soft)", color: "var(--brand)" }}>
              <i className="ph ph-user-circle" style={{ fontSize: "27px" }} />
            </div>
            <div className="min-w-0">
              <div className="text-[9.5px] font-bold tracking-[.16em] uppercase" style={{ color: "var(--brand)" }}>Cuenta de usuario</div>
              <div className="text-[20px] font-bold mt-1.5 tracking-[-.025em]" style={{ color: "var(--tx)" }}>Perfil y seguridad</div>
              <div className="text-[10.5px] mt-1.5 max-w-[650px]" style={{ color: "var(--tx-dim)" }}>
                Consulta la información asociada a tu cuenta y administra tus credenciales de acceso a la consola central.
              </div>
            </div>
          </div>
        </section>

        {error && (
          <div className="soc-panel rounded-2xl p-10 text-center" style={{ color: "var(--crit)" }}>
            <div className="w-12 h-12 rounded-2xl mx-auto grid place-items-center mb-3" style={{ background: "var(--crit-soft)" }}>
              <i className="ph ph-warning-circle" style={{ fontSize: "22px" }} />
            </div>
            <div className="text-[12px] font-semibold">No se pudo cargar tu perfil</div>
            <div className="text-[10px] mt-1" style={{ color: "var(--tx-mute)" }}>{error}</div>
          </div>
        )}

        {loading && !data && !error && (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <div className="h-[390px] rounded-2xl animate-pulse" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }} />
            <div className="h-[390px] rounded-2xl animate-pulse" style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }} />
          </div>
        )}

        {data && (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 items-start">
            <ProfileInfoCard data={data} roleLabel={roleLabel} onSaved={load} />
            <ProfileSecurityCard />
          </div>
        )}
      </div>
    </main>
  );
}
