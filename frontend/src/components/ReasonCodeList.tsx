import { OVERLAY_CODES } from "../utils/theme";

interface Props {
  codes: string[];
  emptyText?: string;
}

// Renders reason-code chips. Codes contributed by the client add-on overlay are
// highlighted in indigo so the client can see the enhancement at a glance.
export default function ReasonCodeList({ codes, emptyText = "—" }: Props) {
  if (!codes.length) return <span className="text-slate-400">{emptyText}</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {codes.map((code) => {
        const overlay = OVERLAY_CODES.has(code);
        return (
          <span
            key={code}
            title={overlay ? "Client add-on overlay signal" : "Step 1 signal"}
            className={`rounded px-1.5 py-0.5 text-[11px] font-medium ring-1 ring-inset ${
              overlay
                ? "bg-indigo-50 text-indigo-700 ring-indigo-200"
                : "bg-slate-50 text-slate-600 ring-slate-200"
            }`}
          >
            {code}
          </span>
        );
      })}
    </div>
  );
}
