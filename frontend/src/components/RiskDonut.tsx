import type { RiskDistributionItem } from "../types/dashboard";

interface RiskDonutProps {
  data: RiskDistributionItem[];
  total: number;
}

const R = 54;
const CIRC = 2 * Math.PI * R;

export default function RiskDonut({ data, total }: RiskDonutProps) {
  const sum = data.reduce((s, d) => s + d.count, 0) || 1;

  let cumulative = 0;
  const segments = data.map((d) => {
    const len = (d.count / sum) * CIRC;
    const offset = -((cumulative / sum) * CIRC);
    cumulative += d.count;
    return { ...d, len, offset };
  });

  return (
    <section
      className="rounded-[10px] border p-4"
      style={{ background: "var(--surf)", borderColor: "var(--line)", boxShadow: "var(--shadow)" }}
    >
      <h2 className="text-[14.5px] font-semibold m-0" style={{ color: "var(--tx)" }}>
        Estado de riesgo de los endpoints
      </h2>

      <div className="flex items-center gap-4.5 mt-3.5">
        <div className="relative w-[150px] h-[150px] shrink-0">
          <svg viewBox="0 0 140 140" className="w-full h-full" style={{ transform: "rotate(-90deg)" }}>
            <circle cx="70" cy="70" r={R} fill="none" stroke="var(--surf3)" strokeWidth="15" />
            {segments
              .filter((s) => s.len > 0)
              .map((s) => (
                <circle
                  key={s.level}
                  cx="70"
                  cy="70"
                  r={R}
                  fill="none"
                  stroke={s.color}
                  strokeWidth="15"
                  strokeDasharray={`${s.len.toFixed(1)} ${(CIRC - s.len).toFixed(1)}`}
                  strokeDashoffset={s.offset.toFixed(1)}
                />
              ))}
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center text-center pointer-events-none">
            <div className="text-[30px] font-semibold tracking-tight leading-none" style={{ color: "var(--tx)" }}>
              {total}
            </div>
            <div className="text-[9.5px] mt-1 leading-tight max-w-[78px]" style={{ color: "var(--tx-mute)" }}>
              Endpoints monitoreados
            </div>
          </div>
        </div>

        <div className="flex-1 flex flex-col gap-2 min-w-0">
          {data.map((item) => (
            <div key={item.level} className="flex items-center gap-2 text-[12.5px]">
              <span className="w-2 h-2 rounded-sm shrink-0" style={{ background: item.color }} />
              <span style={{ color: item.level === "CRITICAL" ? item.color : "var(--tx-dim)", fontWeight: item.level === "CRITICAL" ? 600 : 400 }}>
                {item.label}
              </span>
              <span
                className="ml-auto font-semibold"
                style={{ color: item.level === "CRITICAL" ? item.color : "var(--tx)", fontWeight: item.level === "CRITICAL" ? 700 : 600 }}
              >
                {item.count}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
