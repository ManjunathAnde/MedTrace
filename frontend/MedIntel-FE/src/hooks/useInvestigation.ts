import { useCallback, useState } from "react";
import axios from "axios";
import { investigate as investigateRequest } from "../api/investigate";
import type { InvestigateResponse } from "../api/types";

export type { InvestigateResponse };

const MIN_SUCCESS_LOADING_MS = 2000;

export type InvestigationError = {
  status?: number;
  title: string;
  message: string;
};

// Every expected outcome is HTTP 200 with a status (PROJECT.md Section 10);
// only malformed requests and server errors land here.
export function messageForError(caught: unknown): InvestigationError {
  const status = axios.isAxiosError(caught) ? caught.response?.status : undefined;
  if (status === 503) {
    return {
      status,
      title: "Drug name lookup is unavailable",
      message: "RxNorm, the service MedTrace uses to recognize medication names, isn't responding. Please try again in a moment.",
    };
  }
  if (import.meta.env.DEV && !status && caught instanceof Error && caught.message.startsWith("Mock mode:")) {
    return { title: "No saved response", message: caught.message };
  }
  return {
    status,
    title: "Something went wrong",
    message: "The request could not be completed. Please try again in a moment.",
  };
}

export function wait(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export function useInvestigation() {
  const [query, setQuery] = useState("");
  const [report, setReport] = useState<InvestigateResponse | null>(null);
  const [error, setError] = useState<InvestigationError | null>(null);
  const [loading, setLoading] = useState(false);

  const investigate = useCallback(async (query: string) => {
    const trimmed = query.trim();
    if (!trimmed) return;

    setQuery(trimmed);
    setLoading(true);
    setError(null);
    setReport(null);
    const startedAt = window.performance.now();

    try {
      const payload = await investigateRequest(trimmed);
      const remainingLoadingTime = MIN_SUCCESS_LOADING_MS - (window.performance.now() - startedAt);
      if (remainingLoadingTime > 0) {
        await wait(remainingLoadingTime);
      }
      setReport(payload);
      setLoading(false);
    } catch (caught) {
      setError(messageForError(caught));
      setLoading(false);
    }
  }, []);

  return {
    query,
    loading,
    report,
    error,
    investigate,
  };
}
