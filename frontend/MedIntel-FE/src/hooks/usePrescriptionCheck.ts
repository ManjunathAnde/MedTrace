import { useCallback, useState } from "react";
import { prescriptionCheck } from "../api/prescriptionCheck";
import type { PrescriptionCheckResponse } from "../api/types";
import { InvestigationError, messageForError, wait } from "./useInvestigation";

const MIN_SUCCESS_LOADING_MS = 2000;

export function usePrescriptionCheck() {
  const [result, setResult] = useState<PrescriptionCheckResponse | null>(null);
  const [error, setError] = useState<InvestigationError | null>(null);
  const [loading, setLoading] = useState(false);

  const run = useCallback(async (drugs: string[]) => {
    if (!drugs.length) return;

    setLoading(true);
    setError(null);
    setResult(null);
    const startedAt = window.performance.now();

    try {
      const payload = await prescriptionCheck(drugs);
      const remainingLoadingTime = MIN_SUCCESS_LOADING_MS - (window.performance.now() - startedAt);
      if (remainingLoadingTime > 0) {
        await wait(remainingLoadingTime);
      }
      setResult(payload);
    } catch (caught) {
      setError(messageForError(caught));
    } finally {
      setLoading(false);
    }
  }, []);

  return { result, error, loading, run };
}
