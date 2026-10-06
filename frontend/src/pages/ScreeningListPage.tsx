import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError, ScreeningSummary, listScreenings } from "../api/client";
import StatusBadge from "../components/StatusBadge";
import { formatDateTime, formatNumber } from "../format";

const POLL_INTERVAL_MS = 5000;
const TERMINAL_STATUSES = new Set(["completed", "failed"]);

export default function ScreeningListPage() {
  const navigate = useNavigate();
  const [screenings, setScreenings] = useState<ScreeningSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function load() {
      try {
        const result = await listScreenings();
        if (cancelled) return;
        setScreenings(result);
        setError(null);
        // Keep refreshing only while something is still queued or running.
        if (result.some((item) => !TERMINAL_STATUSES.has(item.status))) {
          timer = setTimeout(load, POLL_INTERVAL_MS);
        }
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Nie udało się pobrać listy analiz.");
      }
    }

    void load();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, []);

  return (
    <section>
      <div className="page-heading">
        <h1>Analizy</h1>
        <Link to="/new" className="button">
          Nowy screening
        </Link>
      </div>

      {error && <p className="form-error">{error}</p>}
      {!error && screenings === null && <p>Ładowanie…</p>}
      {screenings?.length === 0 && (
        <p>
          Nie ma jeszcze żadnych analiz. <Link to="/new">Uruchom pierwszy screening</Link>.
        </p>
      )}

      {screenings && screenings.length > 0 && (
        <div className="table-scroll">
          <table className="data-table data-table--clickable">
            <thead>
              <tr>
                <th>Utworzono</th>
                <th>Status</th>
                <th>Technologia</th>
                <th>Kraj</th>
                <th className="numeric">Dostępna pow. [m²]</th>
                <th className="numeric">Ostrzeżenia</th>
              </tr>
            </thead>
            <tbody>
              {screenings.map((item) => (
                <tr key={item.id} onClick={() => navigate(`/screenings/${item.id}`)}>
                  <td>
                    <Link to={`/screenings/${item.id}`} onClick={(event) => event.stopPropagation()}>
                      {formatDateTime(item.created_at)}
                    </Link>
                  </td>
                  <td>
                    <StatusBadge status={item.status} />
                  </td>
                  <td>{item.technology}</td>
                  <td>{item.country}</td>
                  <td className="numeric">{formatNumber(item.available_area_square_meters)}</td>
                  <td className="numeric">{item.warnings ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
