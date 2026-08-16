import KpiCards from "../components/KpiCards";
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

export default function DashboardPage({ data }: Props) {
  return (
    <main className="grid grid-cols-12 gap-3.5 px-[22px] pt-[18px] pb-8 content-start">
      <div className="col-span-12">
        <QuickActions />
      </div>

      <div className="col-span-12">
        <KpiCards summary={data.summary} />
      </div>

      <div className="col-span-12 xl:col-span-8">
        <ActivityChart />
      </div>
      <div className="col-span-12 xl:col-span-4">
        <RiskDonut data={data.risk_distribution} total={data.summary.endpoints_total} />
      </div>

      <div className="col-span-12 xl:col-span-7">
        <EndpointsAtRisk endpoints={data.endpoints_at_risk} />
      </div>
      <div className="col-span-12 xl:col-span-5">
        <HoneyfileActivityPanel data={data.honeyfile_activity} />
      </div>

      <div className="col-span-12 xl:col-span-8">
        <RecentAlertsTable alerts={data.recent_alerts} />
      </div>
      <div className="col-span-12 xl:col-span-4 flex flex-col gap-3.5">
        <div className="flex-1 flex flex-col">
          <EndpointStatusPanel status={data.endpoint_status} />
        </div>
        <div className="flex-1 flex flex-col">
          <SystemStatusPanel status={data.system_status} />
        </div>
      </div>

      <div className="col-span-12 xl:col-span-7">
        <TopDetections data={data.top_detections} />
      </div>
      <div className="col-span-12 xl:col-span-5">
        <RecentActivityTimeline items={data.recent_activity} />
      </div>

      <div className="col-span-12 text-center text-[10.5px] pt-2" style={{ color: "var(--tx-mute)" }}>
        Última actualización: {data.generated_at} · se actualiza automáticamente cada 20s
      </div>
    </main>
  );
}
