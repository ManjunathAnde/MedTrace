// Dev-only mock mode (VITE_USE_MOCKS=true on the dev server): serves responses
// saved from the cp3/cp4/cp5 smoke runs instead of calling the backend. Only
// ever loaded through a dynamic import behind `import.meta.env.DEV`, so
// production builds never include it.
import type { InvestigateResponse, PrescriptionCheckResponse } from "../api/types";

if (!import.meta.env.DEV) {
  throw new Error("MedTrace mocks must never load outside the dev server");
}

// `source` records how each file was made: captured live, live with no LLM call,
// or replayed through the real endpoint with a smoke run's recorded LLM outputs.
type Saved<Req, Body> = { source: string; request: Req; http: number; body: Body };
type SavedAsk = Saved<{ query: string }, InvestigateResponse>;
type SavedCheck = Saved<{ drugs: string[] }, PrescriptionCheckResponse>;

const files = import.meta.glob<SavedAsk | SavedCheck>("./responses/*.json", { eager: true, import: "default" });

const asks: SavedAsk[] = [];
const checks: SavedCheck[] = [];
for (const [path, saved] of Object.entries(files)) {
  if (path.includes("/ask_")) asks.push(saved as SavedAsk);
  else checks.push(saved as SavedCheck);
}

const MOCK_LATENCY_MS = 600;

function normalizeQuery(query: string) {
  return query.trim().toLowerCase().replace(/\s+/g, " ").replace(/[?.!]+$/, "");
}

function drugKey(drugs: string[]) {
  return drugs.map((d) => d.trim().toLowerCase()).filter(Boolean).sort().join("|");
}

function wait(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export class MockNotFoundError extends Error {}

export const savedQueries = asks.map((a) => a.request.query);
export const savedDrugLists = checks.map((c) => c.request.drugs);

export async function mockInvestigate(query: string): Promise<InvestigateResponse> {
  await wait(MOCK_LATENCY_MS);
  const saved = asks.find((a) => normalizeQuery(a.request.query) === normalizeQuery(query));
  if (!saved) throw new MockNotFoundError(`Mock mode: no saved response for "${query}".`);
  return saved.body;
}

export async function mockPrescriptionCheck(drugs: string[]): Promise<PrescriptionCheckResponse> {
  await wait(MOCK_LATENCY_MS);
  const saved = checks.find((c) => drugKey(c.request.drugs) === drugKey(drugs));
  if (!saved) throw new MockNotFoundError(`Mock mode: no saved response for ${drugs.join(", ")}.`);
  return saved.body;
}
