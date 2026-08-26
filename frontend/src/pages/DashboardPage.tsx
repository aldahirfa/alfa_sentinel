import SecurityOverviewHero from "../components/SecurityOverviewHero";
import RiskDonut from "../components/RiskDonut";
import ActivityChart from "../components/ActivityChart";
import EndpointsAtRisk from "../components/EndpointsAtRisk";
import RecentAlertsTable from "../components/RecentAlertsTable";
import HoneyfileActivityPanel from "../components/HoneyfileActivityPanel";
import EndpointStatusPanel from "../components/EndpointStatusPanel";
import TopDetections from "../components/TopDetections";
import RecentActivityTimeline from "../components/RecentActivityTimeline";
import SystemStatusPanel from "../components/SystemStatusPanel";
import QuickActions from "../components/QuickActions";
import type { DashboardOverview } from "../types/dashboard";

interface Props {
  data: DashboardOverview;
}

function SectionLabel({ eyebrow, title, description }: { eyebrow: string; title: string; description?: string }) {
  return (
    <div className="col-span-12 mt-2 pb-3 border-b" style={{ borderColor: "var(--line-soft)" }}>
      <div className="text-[9px] font-bold tracking-[.16em] uppercase" style={{ color: "var(--brand)" }}>
        {eyebrow}
      </div>
      <div className="text-[14px] font-semibold mt-1" style={{ color: "var(--tx)" }}>{title}</div>
      {description && <div className="text-[10.5px] mt-1" style={{ color: "var(--tx-mute)" }}>{description}</div>}
    </div>
  );
}

export default function DashboardPage({ data }: Props) {
  return (
    <main className="soc-page grid grid-cols-12 gap-4 px-[22px] pt-[18px] pb-8 content-start">
      <div className="col-span-12 xl:col-span-8">
        <SecurityOverviewHero data={data} />
      </div>
      <div className="col-span-12 xl:col-span-4">
        <RiskDonut data={data.risk_distribution} total={data.summary.endpoints_total} />
      </div>

      <div className="col-span-12">
        <QuickActions />
      </div>

      <SectionLabel
        eyebrow="Monitoreo continuo"
        title="Telemetría y disponibilidad"
        description="Comportamiento de las señales de seguridad y estado operativo de los endpoints y servicios centrales."
      />
      <div className="col-span-12 xl:col-span-8">
        <ActivityChart />
      </div>
      <div className="col-span-12 xl:col-span-4 flex flex-col gap-4">
        <div className="flex-1 flex flex-col"><EndpointStatusPanel status={data.endpoint_status} /></div>
        <div className="flex-1 flex flex-col"><SystemStatusPanel status={data.system_status} /></div>
      </div>

      <SectionLabel
        eyebrow="Atención prioritaria"
        title="Elementos que requieren revisión"
        description="Endpoints con riesgo, activaciones de archivos señuelo y detecciones que necesitan contexto operacional."
      />
      <div className="col-span-12 xl:col-span-7"><EndpointsAtRisk endpoints={data.endpoints_at_risk} /></div>
      <div className="col-span-12 xl:col-span-5"><HoneyfileActivityPanel data={data.honeyfile_activity} /></div>

      <div className="col-span-12"><RecentAlertsTable alerts={data.recent_alerts} /></div>

      <SectionLabel
        eyebrow="Contexto operativo"
        title="Patrones de detección y actividad reciente"
        description="Señales dominantes y secuencia temporal de eventos observados por el Sistema ALFA-Sentinel."
      />
      <div className="col-span-12 xl:col-span-7"><TopDetections data={data.top_detections} /></div>
      <div className="col-span-12 xl:col-span-5"><RecentActivityTimeline items={data.recent_activity} /></div>

      <div className="col-span-12 flex items-center justify-end text-[9.5px] pt-2" style={{ color: "var(--tx-mute)" }}>
        Última actualización: {data.generated_at} · actualización automática cada 20 s
      </div>
    </main>
  );
}
