import type { components } from "./schema";

export type ScreeningSummary = components["schemas"]["ScreeningSummary"];
export type FindingSummary = components["schemas"]["FindingSummary"];
export type ProfileSeries = components["schemas"]["ProfileSeries"];
export type WindResult = components["schemas"]["WindResult"];
export type SolarResult = components["schemas"]["SolarResult"];
export type HybridResult = components["schemas"]["HybridResult"];
export type BatteryResult = components["schemas"]["BatteryResult"];
export type TechnologyResults = components["schemas"]["TechnologyResults"];

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function parseErrorDetail(response: Response): Promise<string> {
  try {
    const body = await response.json();
    const detail = body?.detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail.message === "string") return detail.message;
    return JSON.stringify(detail ?? body);
  } catch {
    return response.statusText;
  }
}

async function asJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
  return (await response.json()) as T;
}

export interface NewScreeningInput {
  site: File;
  constraints: File;
  rules: File;
  technology: string;
  country: string;
  analysisDate?: string;
}

export async function createScreening(input: NewScreeningInput): Promise<ScreeningSummary> {
  const body = new FormData();
  body.set("site", input.site);
  body.set("constraints", input.constraints);
  body.set("rules", input.rules);
  body.set("technology", input.technology);
  body.set("country", input.country);
  if (input.analysisDate) body.set("analysis_date", input.analysisDate);

  const response = await fetch(`${API_BASE_URL}/v1/screenings`, {
    method: "POST",
    body,
  });
  return asJson<ScreeningSummary>(response);
}

export async function getScreening(screeningId: string): Promise<ScreeningSummary> {
  const response = await fetch(`${API_BASE_URL}/v1/screenings/${screeningId}`);
  return asJson<ScreeningSummary>(response);
}

export function screeningReportUrl(screeningId: string): string {
  return `${API_BASE_URL}/v1/screenings/${screeningId}/report`;
}

export function screeningLayerUrl(screeningId: string, layer: "available" | "excluded"): string {
  return `${API_BASE_URL}/v1/screenings/${screeningId}/layers/${layer}`;
}

export async function getScreeningLayer(
  screeningId: string,
  layer: "available" | "excluded",
): Promise<GeoJSON.FeatureCollection> {
  const response = await fetch(screeningLayerUrl(screeningId, layer));
  return asJson<GeoJSON.FeatureCollection>(response);
}

export async function listScreenings(limit = 50): Promise<ScreeningSummary[]> {
  const response = await fetch(`${API_BASE_URL}/v1/screenings?limit=${limit}`);
  return asJson<ScreeningSummary[]>(response);
}

export async function getTechnologyResults(screeningId: string): Promise<TechnologyResults> {
  const response = await fetch(`${API_BASE_URL}/v1/screenings/${screeningId}/technologies`);
  return asJson<TechnologyResults>(response);
}

/** Form fields of a technology request; empty strings and null files are left out,
 * so optional API parameters fall back to their server-side defaults. */
export type TechnologyForm = Record<string, string | boolean | File | null | undefined>;

function toFormData(fields: TechnologyForm): FormData {
  const body = new FormData();
  for (const [name, value] of Object.entries(fields)) {
    if (value === null || value === undefined || value === "") continue;
    body.set(name, value instanceof File ? value : String(value));
  }
  return body;
}

async function postTechnology<T>(
  screeningId: string,
  endpoint: string,
  fields: TechnologyForm,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}/v1/screenings/${screeningId}/${endpoint}`, {
    method: "POST",
    body: toFormData(fields),
  });
  return asJson<T>(response);
}

export function createTurbineLayout(screeningId: string, fields: TechnologyForm) {
  return postTechnology<WindResult>(screeningId, "turbine-layout", fields);
}

export function createSolarArray(screeningId: string, fields: TechnologyForm) {
  return postTechnology<SolarResult>(screeningId, "solar-array", fields);
}

export function createHybrid(screeningId: string, fields: TechnologyForm) {
  return postTechnology<HybridResult>(screeningId, "hybrid", fields);
}

export function createBatteryDispatch(screeningId: string, fields: TechnologyForm) {
  return postTechnology<BatteryResult>(screeningId, "battery-dispatch", fields);
}
