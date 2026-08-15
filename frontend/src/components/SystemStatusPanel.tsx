import type { SystemStatus } from "../types/dashboard";

interface Props {
  status: SystemStatus;
}

function StatusRow({ label, ok, okLabel }: { label: string; ok: boolean; okLabel: string }) {
  return (
    <div className="flex items-center gap-2 text-[12.5px] py-1" style={{ color: "var(--tx-dim)" }}>
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: ok ? "var(--ok)" : "var(--crit)" }} />
      {label}
      <span className="ml-auto text-[11.5px]" style={{ color: "var(--tx-mute)" }}>
        {ok ? okLabel : "Con problemas"}
      </span>
    </div>
  );
}

export default function SystemStatusPanel({ status }: Props) {
  return (
    <section
      className="rounded-[10px] border p-4"
      style={{ background: "var(--surf)", borderColor: "var(--line)", boxShadow: "var(--shadow)" }}
    >
      <h2 className="text-[14.5px] font-semibold m-0" style={{ color: "var(--tx)" }}>Estado de ALFA_SENTINEL</h2>

      <div className="flex flex-col gap-2 mt-3">
        <StatusRow label="API" ok={status.api_ok} okLabel="Operativa" />
        <StatusRow label="Base de datos" ok={status.db_ok} okLabel="Operativa" />
        <StatusRow label="Comunicación con agentes" ok={status.agents_comm_ok} okLabel="Operativa" />
        <StatusRow label="Motor de detección" ok={status.detection_engine_ok} okLabel="Operativo" />
      </div>

      <div className="mt-3.5 pt-3 border-t flex flex-col gap-1.5 text-[11.5px]" style={{ borderColor: "var(--line-soft)", color: "var(--tx-mute)" }}>
        <div className="flex">
          <span>Agentes conectados</span>
          <span className="ml-auto font-medium" style={{ color: "var(--tx-dim)" }}>
            {status.agents_connected}/{status.agents_total}
          </span>
        </div>
        <div className="flex">
          <span>Última sincronización</span>
          <span className="ml-auto" style={{ color: "var(--tx-dim)" }}>{status.last_sync_ago}</span>
        </div>
      </div>
    </section>
  );
}
