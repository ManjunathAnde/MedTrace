import { Card } from "../Card";
import { InfoPanel } from "./InfoPanel";
import { ReportHeader } from "./ReportHeader";
import { ReportSections } from "./ReportSections";
import { createReportView } from "./reportUtils";
import { InvestigationResponse } from "../../hooks/useInvestigation";

export function ReportView({ data }: { data: InvestigationResponse }) {
  const report = createReportView(data);

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
      <Card className="overflow-hidden">
        <ReportHeader report={report} />
        <ReportSections report={report} />
      </Card>
      <InfoPanel report={report} />
    </div>
  );
}
