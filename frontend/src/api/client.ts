import type { components } from "./schema";

export type ScreeningSummary = components["schemas"]["ScreeningSummary"];
export type FindingSummary = components["schemas"]["FindingSummary"];

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
