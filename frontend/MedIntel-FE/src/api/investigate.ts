import { apiClient } from "./client";
import type { InvestigateResponse } from "./types";

export type { InvestigateResponse };

export async function investigate(query: string): Promise<InvestigateResponse> {
  // Dev-only mock mode: the condition is false in production builds, so the
  // mocks chunk is never bundled or loaded there.
  if (import.meta.env.DEV && import.meta.env.VITE_USE_MOCKS === "true") {
    const { mockInvestigate } = await import("../mocks");
    return mockInvestigate(query);
  }

  const response = await apiClient.post<InvestigateResponse>("/investigate", {
    query,
  });

  return response.data;
}
