import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError, createScreening } from "../api/client";

export default function NewScreeningPage() {
  const navigate = useNavigate();
  const [technology, setTechnology] = useState("wind");
  const [country, setCountry] = useState("PL");
  const [analysisDate, setAnalysisDate] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    const form = event.currentTarget;
    const site = (form.elements.namedItem("site") as HTMLInputElement).files?.[0];
    const constraints = (form.elements.namedItem("constraints") as HTMLInputElement).files?.[0];
    const rules = (form.elements.namedItem("rules") as HTMLInputElement).files?.[0];
    if (!site || !constraints || !rules) {
      setError("Wybierz wszystkie trzy pliki: granicę, ograniczenia i reguły.");
      return;
    }

    setSubmitting(true);
    try {
      const summary = await createScreening({
        site,
        constraints,
        rules,
        technology,
        country,
        analysisDate: analysisDate || undefined,
      });
      navigate(`/screenings/${summary.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Nie udało się utworzyć screeningu.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section>
      <h1>Nowy screening</h1>
      <form onSubmit={handleSubmit} className="new-screening-form">
        <label>
          Granica terenu (GeoJSON)
          <input type="file" name="site" accept=".geojson,.json" required />
        </label>
        <label>
          Warstwy ograniczeń (GeoJSON)
          <input type="file" name="constraints" accept=".geojson,.json" required />
        </label>
        <label>
          Reguły (YAML)
          <input type="file" name="rules" accept=".yaml,.yml" required />
        </label>
        <label>
          Technologia
          <input
            type="text"
            value={technology}
            onChange={(e) => setTechnology(e.target.value)}
            placeholder="wind"
            required
          />
        </label>
        <label>
          Kraj
          <input type="text" value={country} onChange={(e) => setCountry(e.target.value)} required />
        </label>
        <label>
          Data analizy (opcjonalnie, domyślnie dziś)
          <input
            type="date"
            value={analysisDate}
            onChange={(e) => setAnalysisDate(e.target.value)}
          />
        </label>
        <button type="submit" disabled={submitting}>
          {submitting ? "Wysyłanie…" : "Uruchom screening"}
        </button>
        {error && <p className="form-error">{error}</p>}
      </form>
    </section>
  );
}
