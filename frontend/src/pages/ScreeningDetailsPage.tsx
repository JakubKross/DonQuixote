import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError, ScreeningSummary, getScreening, screeningReportUrl } from "../api/client";
import FindingsTable from "../components/FindingsTable";
import ScreeningMap from "../components/ScreeningMap";
import StatusBadge from "../components/StatusBadge";

const POLL_INTERVAL_MS = 2000;
const TERMINAL_STATUSES = new Set(["completed", "failed"]);

export default function ScreeningDetailsPage() {
  const { screeningId } = useParams<{ screeningId: string }>();
  const [summary, setSummary] = useState<ScreeningSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!screeningId) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function poll() {
      try {
        const result = await getScreening(screeningId!);
        if (cancelled) return;
        setSummary(result);
        if (!TERMINAL_STATUSES.has(result.status)) {
          timer = setTimeout(poll, POLL_INTERVAL_MS);
        }
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Nie udało się pobrać screeningu.");
      }
    }

    void poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [screeningId]);

  if (!screeningId) return <p>Brak identyfikatora screeningu.</p>;
  if (error) return <p className="form-error">{error}</p>;
  if (!summary) return <p>Ładowanie…</p>;

  return (
    <section>
      <h1>Screening {summary.id}</h1>
      <p>
        <StatusBadge status={summary.status} /> — {summary.technology} / {summary.country}
      </p>

      {summary.status === "failed" && summary.error_message && (
        <p className="form-error">{summary.error_message}</p>
      )}

      {summary.initial_area_square_meters != null && (
        <table className="area-summary">
          <tbody>
            <tr>
              <th>Powierzchnia początkowa</th>
              <td>{summary.initial_area_square_meters.toFixed(1)} m²</td>
            </tr>
            <tr>
              <th>Powierzchnia wykluczona</th>
              <td>{summary.excluded_area_square_meters?.toFixed(1)} m²</td>
            </tr>
            <tr>
              <th>Powierzchnia dostępna</th>
              <td>{summary.available_area_square_meters?.toFixed(1)} m²</td>
            </tr>
          </tbody>
        </table>
      )}

      <FindingsTable findings={summary.findings ?? []} />

      {summary.status === "completed" && (
        <>
          <p>
            <a href={screeningReportUrl(summary.id)} target="_blank" rel="noreferrer">
              Pełny raport tekstowy
            </a>
          </p>
          <ScreeningMap screeningId={summary.id} />
        </>
      )}
    </section>
  );
}
