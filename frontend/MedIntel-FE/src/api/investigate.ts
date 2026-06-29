import { apiClient } from "./client";

export type InvestigationResponse = Record<string, unknown>;

export async function investigate(query: string): Promise<InvestigationResponse> {
  const response = await apiClient.post<InvestigationResponse>("/investigate", {
    query,
  });

  return response.data;
}
