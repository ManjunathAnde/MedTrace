import { ArrowRightLeft, CircleHelp, CloudOff, HeartHandshake, SearchX, ShieldAlert, Split } from "lucide-react";
import type { InvestigateResponse } from "../../api/types";
import { GapsBox } from "../evidence/GapsBox";
import { usePassagePanel } from "../evidence/PassagePanel";
import { RemovedClaims } from "../evidence/RemovedClaims";
import { StatusCard } from "../StatusCard";
import { Button } from "../ui/Button";
import { AnswerView } from "./AnswerView";

type AskResultProps = {
  data: InvestigateResponse;
  onOpenPrescriptionCheck: (drugs: string[]) => void;
};

function InsufficientEvidence({ data }: { data: InvestigateResponse }) {
  const { panel, openPassage } = usePassagePanel();
  return (
    <StatusCard
      tone="slate"
      icon={SearchX}
      eyebrow="Insufficient evidence"
      title="Not enough evidence in FDA sources to answer this."
    >
      <div className="space-y-3">
        <GapsBox gaps={data.gaps} />
        <RemovedClaims removed={data.removed} evidence={data.evidence} onOpen={openPassage} />
      </div>
      {panel}
    </StatusCard>
  );
}

// Status -> card (PROJECT.md Section 11 item 7); ANSWERED and PARTIAL show the claims.
export function AskResult({ data, onOpenPrescriptionCheck }: AskResultProps) {
  switch (data.status) {
    case "ANSWERED":
    case "PARTIAL":
      return <AnswerView data={data} />;
    case "INSUFFICIENT_EVIDENCE":
      return <InsufficientEvidence data={data} />;
    case "BLOCKED":
      return data.block_type === "SELF_HARM_RISK" ? (
        <StatusCard tone="sky" icon={HeartHandshake} eyebrow="Support is available" title="You don't have to go through this alone" message={data.message} />
      ) : (
        <StatusCard tone="amber" icon={ShieldAlert} eyebrow="Personal medical advice" title="MedTrace can't advise on your own treatment" message={data.message} />
      );
    case "REDIRECT":
      return (
        <StatusCard
          tone="emerald"
          icon={ArrowRightLeft}
          eyebrow="Interaction question"
          title="Check these medications together"
          message={`This question is about how ${(data.redirect?.drugs ?? []).join(" and ")} interact. Prescription Check reviews both FDA labels side by side.`}
        >
          <Button onClick={() => onOpenPrescriptionCheck(data.redirect?.drugs ?? [])}>
            Check these together in Prescription Check <ArrowRightLeft size={18} />
          </Button>
        </StatusCard>
      );
    case "NOT_RECOGNIZED":
      return <StatusCard tone="slate" icon={SearchX} eyebrow="Medication not recognized" title="We couldn't match that name" message={data.message} />;
    case "NO_DRUG":
      return <StatusCard tone="slate" icon={CircleHelp} eyebrow="No medication named" title="Which medication do you mean?" message={data.message} />;
    case "ONE_AT_A_TIME":
      return (
        <StatusCard tone="slate" icon={Split} eyebrow="Several medications" title="One medication at a time" message={data.message}>
          <Button variant="outline" onClick={() => onOpenPrescriptionCheck([])}>
            Open Prescription Check <ArrowRightLeft size={18} />
          </Button>
        </StatusCard>
      );
    case "UNAVAILABLE":
    default:
      return <StatusCard tone="amber" icon={CloudOff} eyebrow="Temporarily unavailable" title="MedTrace couldn't finish its checks" message={data.message} />;
  }
}
