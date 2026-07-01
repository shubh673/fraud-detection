import { NavLink, Outlet } from "react-router-dom";

interface NavItem {
  to: string;
  label: string;
  icon: string;
  step?: string;
}

const NAV: { section: string; items: NavItem[] }[] = [
  {
    section: "Overview",
    items: [{ to: "/", label: "Executive Overview", icon: "▦" }],
  },
  {
    section: "Step 1 — Real-Time Triage",
    items: [
      { to: "/step1", label: "Fraud Triage", icon: "◎", step: "Step 1" },
      { to: "/overlay", label: "Overlay & Simulator", icon: "⚙", step: "Step 1+" },
    ],
  },
  {
    section: "Client Add-On Detectors",
    items: [
      { to: "/bin-attack", label: "BIN Attack Detection", icon: "▲", step: "Step 3" },
      { to: "/ip-repetition", label: "Same-IP Repetitive Auth", icon: "≣", step: "Step 3" },
      { to: "/merchants", label: "Merchant Blacklist", icon: "⛔", step: "Step 1+" },
    ],
  },
  {
    section: "Operations",
    items: [
      { to: "/queue", label: "Analyst Alert Queue", icon: "☰" },
      { to: "/summary", label: "Business Summary", icon: "★" },
    ],
  },
];

export default function Layout() {
  return (
    <div className="flex min-h-screen bg-[#0a0a0a]">
      {/* Sidebar */}
      <aside className="hidden w-64 shrink-0 flex-col bg-[var(--navy-900)] text-slate-300 lg:flex">
        <div className="flex items-center gap-2 border-b border-white/10 px-5 py-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-yellow-400 text-sm font-bold text-black">
            FD
          </div>
          <div>
            <p className="text-sm font-semibold text-white">FraudGuard</p>
            <p className="text-[11px] text-slate-400">Card & Payment Fraud POC</p>
          </div>
        </div>
        <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-4 thin-scroll">
          {NAV.map((group) => (
            <div key={group.section}>
              <p className="px-2 pb-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                {group.section}
              </p>
              <ul className="space-y-0.5">
                {group.items.map((item) => (
                  <li key={item.to}>
                    <NavLink
                      to={item.to}
                      end={item.to === "/"}
                      className={({ isActive }) =>
                        `flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition ${
                          isActive
                            ? "bg-yellow-400 font-semibold text-black"
                            : "text-slate-300 hover:bg-white/5 hover:text-white"
                        }`
                      }
                    >
                      <span className="w-4 text-center text-xs opacity-80">{item.icon}</span>
                      <span className="flex-1">{item.label}</span>
                      {item.step && (
                        <span className="rounded bg-white/10 px-1.5 py-0.5 text-[9px] font-semibold text-slate-200">
                          {item.step}
                        </span>
                      )}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>
        <div className="border-t border-white/10 px-5 py-3 text-[10px] text-slate-500">
          Synthetic data · POC demo only
        </div>
      </aside>

      {/* Main */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex items-center justify-between border-b border-slate-200 bg-[#161619] px-6 py-3 shadow-sm">
          <div>
            <h2 className="text-sm font-semibold text-slate-800">
              Card & Payment Fraud Detection — Client Showcase
            </h2>
            <p className="text-[11px] text-slate-500">
              Real-time triage · BIN attack · Same-IP repetition · Merchant blacklist
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="hidden rounded-full bg-yellow-400/10 px-2.5 py-1 text-[11px] font-medium text-yellow-300 ring-1 ring-inset ring-yellow-400/30 sm:inline">
              ● Pipeline outputs loaded
            </span>
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-yellow-400 text-xs font-semibold text-black">
              FA
            </div>
          </div>
        </header>

        <main className="mx-auto w-full max-w-[1400px] flex-1 px-6 py-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
