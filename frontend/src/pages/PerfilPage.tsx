import { useEffect, useState } from "react";
import ModuleIntro from "../components/ModuleIntro";
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
    <main className="soc-page module-page flex flex-col gap-4 px-[22px] pt-[18px] pb-10">
      <ModuleIntro
        page="perfil"
        eyebrow="Cuenta de usuario"
        title="Perfil y seguridad"
        description="Consulta la información asociada a tu cuenta y administra tus credenciales de acceso a la consola central."
      />

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
    </main>
  );
}
