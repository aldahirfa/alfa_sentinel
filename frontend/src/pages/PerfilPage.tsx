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
    <main className="flex flex-col gap-3.5 px-[22px] pt-[18px] pb-8 max-w-[560px]">
      {error && (
        <div
          className="rounded-[10px] border p-8 text-center text-sm"
          style={{ background: "var(--surf)", borderColor: "var(--line)", color: "var(--crit)" }}
        >
          {error}
        </div>
      )}

      {loading && !data && !error && (
        <>
          <div className="h-[260px] rounded-[10px] animate-pulse" style={{ background: "var(--surf2)" }} />
          <div className="h-[260px] rounded-[10px] animate-pulse" style={{ background: "var(--surf2)" }} />
        </>
      )}

      {data && (
        <>
          <ProfileInfoCard data={data} roleLabel={roleLabel} onSaved={load} />
          <ProfileSecurityCard />
        </>
      )}
    </main>
  );
}
