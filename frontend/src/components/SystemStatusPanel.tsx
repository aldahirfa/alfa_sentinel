import type { SystemStatus } from "../types/dashboard";

interface Props {
  status: SystemStatus;
}

function ServiceRow({ icon, label, ok, okLabel }: { icon: string; label: string; ok: boolean; okLabel: string }) {
  return (
    <div
      className="flex items-center gap-2.5 px-2.5 py-2 rounded-lg"
      style={{ background: "var(--surf2)", border: "1px solid var(--line-soft)" }}
    >
      <div
        className="w-6 h-6 rounded-md grid place-items-center shrink-0"
        style={{ background: ok ? "var(--ok-soft)" : "var(--crit-soft)", color: ok ? "var(--ok)" : "var(--crit)" }}
      >
        <i className={icon} style={{ fontSize: "12px" }} />
      </div>
      <span className="text-[10.5px] font-medium" style={{ color: "var(--tx-dim)" }}>{label}</span>
      <span className="ml-auto flex items-center gap-1.5 text-[9.5px] font-semibold" style={{ color: ok ? "var(--ok)" : "var(--crit)" }}>
        <span className="w-1.5 h-1.5 rounded-full" style={{ background: ok ? "var(--ok)" : "var(--crit)" }} />
        {ok ? okLabel : "Con problemas"}
      </span>
    </div>
  );
}

export default function SystemStatusPanel({ status }: Props) {
  const services = [status.api_ok, status.db_ok, status.agents_comm_ok, status.detection_engine_ok];
  const healthyServices = services.filter(Boolean).length;
  const allOk = healthyServices === services.length;
  const connectedPct = status.agents_total > 0 ? Math.round((status.agents_connected / status.agents_total) * 100) : 0;

  return (
    <section className="soc-panel rounded-2xl p-5 flex flex-col h-full overflow-hidden">
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-xl grid place-items-center shrink-0" style={{ background: allOk ? "var(--ok-soft)" : "var(--crit-soft)", color: allOk ? "var(--ok)" : "var(--crit)" }}>
          <i className="ph ph-heartbeat" style={{ fontSize: "18px" }} />
        </div>
        <div>
          <div className="text-[9.5px] font-bold tracking-[.15em] uppercase" style={{ color: allOk ? "var(--ok)" : "var(--crit)" }}>
            Servicios centrales
          </div>
          <h2 className="text-[14px] font-semibold m-0 tracking-tight mt-1" style={{ color: "var(--tx)" }}>
            Estado del sistema
          </h2>
        </div>
        <span
          className="ml-auto inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-[9px] font-bold"
          style={{ background: allOk ? "var(--ok-soft)" : "var(--crit-soft)", color: allOk ? "var(--ok)" : "var(--crit)" }}
        >
          {healthyServices}/{services.length} operativos
        </span>
      </div>

      <div className="grid grid-cols-1 gap-1.5 mt-4">
        <ServiceRow icon="ph ph-plugs-connected" label="API" ok={status.api_ok} okLabel="Operativa" />
        <ServiceRow icon="ph ph-database" label="Base de datos" ok={status.db_ok} okLabel="Operativa" />
        <ServiceRow icon="ph ph-broadcast" label="Comunicación con agentes" ok={status.agents_comm_ok} okLabel="Operativa" />
        <ServiceRow icon="ph ph-cpu" label="Motor de detección" ok={status.detection_engine_ok} okLabel="Operativo" />
      </div>

      <div className="mt-4 pt-3.5 border-t" style={{ borderColor: "var(--line-soft)" }}>
        <div className="flex items-center text-[10px]">
          <span style={{ color: "var(--tx-dim)" }}>Agentes conectados</span>
          <span className="ml-auto font-bold tabular-nums" style={{ color: connectedPct >= 90 ? "var(--ok)" : "var(--warn)" }}>
            {status.agents_connected}/{status.agents_total}
          </span>
        </div>
        <div className="h-[5px] rounded-full overflow-hidden mt-2" style={{ background: "var(--surf3)" }}>
          <div
            className="h-full rounded-full"
            style={{ width: `${Math.max(0, Math.min(100, connectedPct))}%`, background: connectedPct >= 90 ? "var(--ok)" : "var(--warn)" }}
          />
        </div>
        <div className="flex items-center mt-2.5 text-[9.5px]" style={{ color: "var(--tx-mute)" }}>
          <span>Última sincronización</span>
          <span className="ml-auto tabular-nums" style={{ color: "var(--tx-dim)" }}>{status.last_sync_ago}</span>
        </div>
      </div>
    </section>
  );
}
