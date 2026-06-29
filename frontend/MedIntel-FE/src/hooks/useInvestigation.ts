import { useCallback, useState } from "react";
import axios from "axios";
import { investigate as investigateRequest } from "../api/investigate";
import type { InvestigationResponse } from "../api/investigate";

export type { InvestigationResponse };

export type InvestigationError = {
  status?: number;
  title: string;
  message: string;
};

function messageForStatus(status?: number): InvestigationError {
  if (status === 403) {
    return {
      status,
      title: "Medical safety review required",
      message: "This request cannot be completed automatically. Please consult a qualified healthcare professional for medication guidance.",
    };
  }

  if (status === 422) {
    return {
      status,
      title: "Medication not found",
      message: "We could not match that query to a medication. Try a generic or brand name with standard spelling.",
    };
  }

  return {
    status,
    title: "Something went wrong",
    message: "The investigation could not be completed. Please try again in a moment.",
  };
}

export function useInvestigation() {
  const [query, setQuery] = useState("");
  const [report, setReport] = useState<InvestigationResponse | null>(null);
  const [error, setError] = useState<InvestigationError | null>(null);
  const [loading, setLoading] = useState(false);

  const investigate = useCallback(async (query: string) => {
    const trimmed = query.trim();
    if (!trimmed) return;

    setQuery(trimmed);
    setLoading(true);
    setError(null);
    setReport(null);

    try {
      const payload = await investigateRequest(trimmed);
      setReport(payload);
    } catch (caught) {
      const status = axios.isAxiosError(caught) ? caught.response?.status : undefined;
      setError(messageForStatus(status));
    } finally {
      setLoading(false);
    }
  }, []);

  return {
    query,
    loading,
    report,
    error,
    investigate,
    data: report,
    isLoading: loading,
  };
}
