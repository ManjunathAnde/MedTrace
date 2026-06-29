import { Info, Menu, Moon, ShieldPlus, Sun, X } from "lucide-react";
import { useState } from "react";
import { MedTraceLogo } from "./MedTraceLogo";
import { Button } from "./ui/Button";
import { cn } from "../lib/utils";

const navItems = [
  { label: "Investigate", icon: ShieldPlus, active: true },
  { label: "How It Works", icon: Info },
];

type SidebarContentProps = {
  isDark: boolean;
  onToggleDarkMode: () => void;
};

function SidebarContent({ isDark, onToggleDarkMode }: SidebarContentProps) {
  return (
    <aside className="flex h-full flex-col justify-between bg-white px-5 py-6 transition-colors dark:bg-slate-950">
      <div>
        <div className="flex items-center gap-3">
          <MedTraceLogo />
          <div>
            <div className="text-2xl font-bold text-emerald-800 dark:text-emerald-300">MedTrace</div>
            <div className="text-sm text-slate-500 dark:text-slate-400">AI Medication Intelligence</div>
          </div>
        </div>

        <nav className="mt-10 space-y-2">
          {navItems.map((item) => (
            <button
              key={item.label}
              className={cn(
                "flex h-12 w-full items-center gap-3 rounded-lg px-4 text-left text-sm font-medium transition",
                item.active
                  ? "bg-emerald-50 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300"
                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-900 dark:hover:text-slate-100",
              )}
            >
              <item.icon size={18} />
              {item.label}
            </button>
          ))}
        </nav>
      </div>

      <div className="space-y-3">
        <div className="rounded-xl border border-emerald-100 bg-emerald-50/50 p-4 text-sm leading-6 text-slate-600 dark:border-emerald-900/50 dark:bg-emerald-950/20 dark:text-slate-300">
          <div className="flex items-center gap-2 font-semibold text-emerald-800 dark:text-emerald-300">
            <ShieldPlus size={17} />
            Evidence-based medication intelligence
          </div>
          <p className="mt-2 text-xs leading-5">Not a substitute for professional medical advice.</p>
        </div>

        <button
          type="button"
          onClick={onToggleDarkMode}
          className="flex w-full items-center justify-between rounded-xl border border-border bg-white p-3 text-sm text-slate-600 transition hover:bg-slate-50 dark:bg-slate-950 dark:text-slate-300 dark:hover:bg-slate-900"
        >
          <div className="flex items-center gap-2">
            {isDark ? <Sun size={17} /> : <Moon size={17} />}
            Dark Mode
          </div>
          <span className={cn("h-6 w-11 rounded-full p-0.5 transition", isDark ? "bg-emerald-500" : "bg-slate-200")}>
            <span className={cn("block h-5 w-5 rounded-full bg-white shadow-sm transition-transform", isDark && "translate-x-5")} />
          </span>
        </button>

        <div className="flex items-center justify-between rounded-xl border border-border bg-white p-3 text-sm dark:bg-slate-950">
          <span className="flex items-center gap-2 text-slate-600 dark:text-slate-300">
            <span className="h-2 w-2 rounded-full bg-emerald-600" />
            Backend Online
          </span>
        </div>
      </div>
    </aside>
  );
}

type SidebarProps = {
  isDark: boolean;
  onToggleDarkMode: () => void;
};

export function Sidebar({ isDark, onToggleDarkMode }: SidebarProps) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <div className="fixed left-0 top-0 z-30 hidden h-screen w-72 border-r border-border lg:block">
        <SidebarContent isDark={isDark} onToggleDarkMode={onToggleDarkMode} />
      </div>
      <div className="sticky top-0 z-40 flex items-center justify-between border-b border-border bg-white/90 px-4 py-3 backdrop-blur transition-colors dark:bg-slate-950/90 lg:hidden">
        <div className="flex items-center gap-2 font-bold text-emerald-800 dark:text-emerald-300">
          <MedTraceLogo compact />
          MedTrace
        </div>
        <Button variant="ghost" className="h-10 w-10 px-0" onClick={() => setOpen(true)} aria-label="Open navigation">
          <Menu size={20} />
        </Button>
      </div>
      {open && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button className="absolute inset-0 bg-slate-950/20" onClick={() => setOpen(false)} aria-label="Close navigation" />
          <div className="absolute left-0 top-0 h-full w-[86vw] max-w-80 border-r border-border bg-white shadow-soft dark:bg-slate-950">
            <Button variant="ghost" className="absolute right-3 top-3 h-9 w-9 px-0" onClick={() => setOpen(false)} aria-label="Close navigation">
              <X size={18} />
            </Button>
            <SidebarContent isDark={isDark} onToggleDarkMode={onToggleDarkMode} />
          </div>
        </div>
      )}
    </>
  );
}
