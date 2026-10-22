import { motion } from "framer-motion";
import { cn } from "../lib/utils";
import { Tab, TABS } from "./Sidebar";

// Top-of-page tabs (Section 11), styled like the old report tabs.
export function TabBar({ tab, onTabChange }: { tab: Tab; onTabChange: (tab: Tab) => void }) {
  return (
    <div className="sticky top-0 z-20 border-b border-border bg-background/90 backdrop-blur">
      <div className="mx-auto flex max-w-[1440px] gap-2 overflow-x-auto px-4 sm:px-6 lg:px-8" role="tablist">
        {TABS.map((item) => (
          <button
            key={item.key}
            role="tab"
            aria-selected={tab === item.key}
            onClick={() => onTabChange(item.key)}
            className={cn(
              "relative flex h-14 shrink-0 items-center gap-2 px-3 text-sm font-medium transition",
              tab === item.key
                ? "text-emerald-800 dark:text-emerald-300"
                : "text-slate-600 hover:text-slate-950 dark:text-slate-400 dark:hover:text-slate-100",
            )}
          >
            <item.icon size={17} />
            {item.label}
            {tab === item.key && <motion.span layoutId="active-tab" className="absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-emerald-700 dark:bg-emerald-400" />}
          </button>
        ))}
      </div>
    </div>
  );
}
