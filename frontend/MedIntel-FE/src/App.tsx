import { useState } from "react";
import { Sidebar, Tab } from "./components/Sidebar";
import { TabBar } from "./components/TabBar";
import { useDarkMode } from "./hooks/useDarkMode";
import { InvestigatePage } from "./pages/InvestigatePage";
import { PrescriptionCheckPage } from "./pages/PrescriptionCheckPage";

export default function App() {
  const { isDark, setIsDark } = useDarkMode();
  const [tab, setTab] = useState<Tab>("ask");
  const [checkDrugs, setCheckDrugs] = useState<string[]>([]);

  // REDIRECT: switch tabs with the drugs pre-filled (Section 11 item 7).
  function openPrescriptionCheck(drugs: string[]) {
    if (drugs.length) setCheckDrugs(drugs.slice(0, 5));
    setTab("check");
  }

  return (
    <div className="min-h-screen bg-background text-foreground transition-colors">
      <Sidebar isDark={isDark} onToggleDarkMode={() => setIsDark((value) => !value)} tab={tab} onTabChange={setTab} />
      <div className="lg:ml-72">
        <div className="h-screen overflow-y-auto">
          <TabBar tab={tab} onTabChange={setTab} />
          {/* Both pages stay mounted so each tab keeps its last result. */}
          <div hidden={tab !== "ask"}>
            <InvestigatePage onOpenPrescriptionCheck={openPrescriptionCheck} />
          </div>
          <div hidden={tab !== "check"}>
            <PrescriptionCheckPage drugs={checkDrugs} onDrugsChange={setCheckDrugs} />
          </div>
        </div>
      </div>
    </div>
  );
}
