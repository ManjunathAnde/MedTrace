import { apiClient } from "./client";
import type { PrescriptionCheckResponse } from "./types";

export type { PrescriptionCheckResponse };

export async function prescriptionCheck(drugs: string[]): Promise<PrescriptionCheckResponse> {
  // Dev-only mock mode: the condition is false in production builds, so the
  // mocks chunk is never bundled or loaded there.
  if (import.meta.env.DEV && import.meta.env.VITE_USE_MOCKS === "true") {
    const { mockPrescriptionCheck } = await import("../mocks");
    return mockPrescriptionCheck(drugs);
  }

  const response = await apiClient.post<PrescriptionCheckResponse>("/prescription-check", {
    drugs,
  });

  return response.data;
}
