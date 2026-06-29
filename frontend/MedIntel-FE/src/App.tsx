import { Sidebar } from "./components/Sidebar";
import { useDarkMode } from "./hooks/useDarkMode";
import { InvestigatePage } from "./pages/InvestigatePage";

export default function App() {
  const { isDark, setIsDark } = useDarkMode();

  return (
    <div className="min-h-screen bg-background text-foreground transition-colors">
      <Sidebar isDark={isDark} onToggleDarkMode={() => setIsDark((value) => !value)} />
      <div className="lg:ml-72">
        <div className="h-screen overflow-y-auto">
          <InvestigatePage />
        </div>
      </div>
    </div>
  );
}
