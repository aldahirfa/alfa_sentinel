import type { TopDetection } from "../types/dashboard";

interface Props {
  data: TopDetection[];
}

export default function TopDetections({ data }: Props) {
  const max = Math.max(1, ...data.map((d) => d.count));

  return (
    <section
      className="rounded-xl border p-5 shadow-sm flex flex-col h-full"
      style={{ background: "var(--surf)", borderColor: "var(--line-soft)" }}
    >
      <h2 className="text-[14px] font-bold tracking-tight m-0" style={{ color: "var(--tx)" }}>
        Principales tipos de detección
      </h2>
      <div className="text-[11.5px] mt-0.5" style={{ color: "var(--tx-mute)" }}>
        Detecciones registradas en las últimas 24 horas
      </div>

      {data.length === 0 ? (
        <p className="text-[12.5px] py-6 text-center" style={{ color: "var(--tx-mute)" }}>
          Todavía no hay detecciones registradas.
        </p>
      ) : (
        <div className="flex flex-col gap-3 mt-auto">
          {data.map((d) => (
            <div key={d.rule_name}>
              <div className="flex text-[12.5px] font-bold mb-1.5">
                <span style={{ color: "var(--tx-dim)" }}>{d.rule_label}</span>
                <span className="ml-auto" style={{ color: "var(--tx)" }}>{d.count}</span>
              </div>
              <div className="h-[7px] rounded overflow-hidden" style={{ background: "var(--surf3)" }}>
                <div
                  className="h-full rounded"
                  style={{ width: `${(d.count / max) * 100}%`, background: "var(--brand)" }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
