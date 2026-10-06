import { FormEvent, ReactNode, useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  ApiError,
  BatteryResult,
  HybridResult,
  ScreeningSummary,
  SolarResult,
  TechnologyForm,
  TechnologyResults,
  WindResult,
  createBatteryDispatch,
  createHybrid,
  createSolarArray,
  createTurbineLayout,
  getScreening,
  getTechnologyResults,
} from "../api/client";
import ProfileChart from "../components/ProfileChart";
import StatusBadge from "../components/StatusBadge";
import { formatNumber, formatPercent } from "../format";

const SERIES_1 = "var(--series-1)";
const SERIES_2 = "var(--series-2)";

/** Read a form into API fields: skips empty file inputs; checkboxes carry value="true". */
function fieldsFromForm(form: HTMLFormElement): TechnologyForm {
  const fields: TechnologyForm = {};
  new FormData(form).forEach((value, name) => {
    if (value instanceof File && value.name === "") return;
    fields[name] = value;
  });
  return fields;
}

type Submit = (fields: TechnologyForm) => Promise<unknown>;

function useTechnologySubmit(submit: Submit, onSaved: () => void) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await submit(fieldsFromForm(event.currentTarget));
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Nie udało się wykonać obliczeń.");
    } finally {
      setSubmitting(false);
    }
  }

  return { submitting, error, handleSubmit };
}

function StatTable({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <table className="area-summary">
      <tbody>
        {rows.map(([label, value]) => (
          <tr key={label}>
            <th>{label}</th>
            <td className="numeric">{value}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

interface SectionProps {
  title: string;
  description: string;
  disabledReason?: string | null;
  submitLabel: string;
  submit: Submit;
  onSaved: () => void;
  fields: ReactNode;
  children: ReactNode;
}

function TechnologySection({
  title,
  description,
  disabledReason,
  submitLabel,
  submit,
  onSaved,
  fields,
  children,
}: SectionProps) {
  const { submitting, error, handleSubmit } = useTechnologySubmit(submit, onSaved);
  return (
    <section className="technology-section">
      <h2>{title}</h2>
      <p className="muted">{description}</p>
      {disabledReason ? (
        <p className="muted">{disabledReason}</p>
      ) : (
        <form onSubmit={handleSubmit} className="technology-form">
          <fieldset disabled={submitting}>
            <div className="technology-form__grid">{fields}</div>
            <button type="submit">{submitting ? "Obliczanie…" : submitLabel}</button>
          </fieldset>
          {error && <p className="form-error">{error}</p>}
        </form>
      )}
      {children}
    </section>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label>
      {label}
      {children}
    </label>
  );
}

function CatalogModelFields({ prefix }: { prefix: string }) {
  return (
    <>
      <Field label="Producent (opcjonalnie)">
        <input type="text" name={`${prefix}_manufacturer`} />
      </Field>
      <Field label="Model (opcjonalnie)">
        <input type="text" name={`${prefix}_model`} />
      </Field>
    </>
  );
}

function SimulationFactorFields() {
  return (
    <>
      <Field label="Dostępność techniczna (0–1)">
        <input type="number" name="technical_availability" min={0} max={1} step="any" defaultValue={1} />
      </Field>
      <Field label="Współczynnik strat (0–1)">
        <input type="number" name="loss_factor" min={0} max={1} step="any" defaultValue={0} />
      </Field>
    </>
  );
}

function WindResultView({ wind }: { wind: WindResult }) {
  const simulation = wind.simulation;
  return (
    <div className="technology-result">
      <h3>
        Wynik: {wind.turbine_manufacturer} {wind.turbine_model}
      </h3>
      <StatTable
        rows={[
          ["Liczba turbin", wind.turbine_count],
          ["Moc zainstalowana", `${formatNumber((wind.turbine_count * wind.rated_power_kw) / 1000, 2)} MW`],
          ["Odstęp", `${formatNumber(wind.spacing_rotor_diameters)} D`],
          ...(simulation
            ? ([
                ["Energia bez wake", `${formatNumber(simulation.no_wake_energy_mwh, 2)} MWh`],
                ["Energia z wake", `${formatNumber(simulation.wake_energy_mwh, 2)} MWh`],
                [
                  "Straty wake",
                  `${formatNumber(simulation.wake_loss_mwh, 2)} MWh (${formatPercent(simulation.wake_loss_fraction)})`,
                ],
              ] as [string, ReactNode][])
            : []),
        ]}
      />
      {simulation ? (
        <ProfileChart
          title={`Produkcja farmy z uwzględnieniem wake (${simulation.simulator})`}
          timestamps={simulation.wake_profile.timestamps}
          series={[{ name: "Produkcja z wake", values: simulation.wake_profile.power_mw, color: SERIES_1 }]}
          unit="MW"
        />
      ) : (
        <p className="muted">
          {wind.turbine_count === 0
            ? "Na dostępnym obszarze nie zmieściła się żadna turbina."
            : "Bez szeregu wiatrowego — produkcja nie została policzona."}
        </p>
      )}
    </div>
  );
}

function SolarResultView({ solar }: { solar: SolarResult }) {
  const simulation = solar.simulation;
  return (
    <div className="technology-result">
      <h3>
        Wynik: {solar.module_manufacturer} {solar.module_model}
      </h3>
      <StatTable
        rows={[
          ["Liczba modułów", solar.module_count],
          ["Moc zainstalowana", `${formatNumber(solar.installed_capacity_kwp, 2)} kWp`],
          ["Zajęta powierzchnia", `${formatNumber(solar.used_area_m2)} m²`],
          ["GCR", formatNumber(solar.ground_coverage_ratio, 2)],
          ...(simulation
            ? ([
                ["Energia DC", `${formatNumber(simulation.dc_energy_mwh, 3)} MWh`],
                ["Energia AC", `${formatNumber(simulation.ac_energy_mwh, 3)} MWh`],
                [
                  "Straty inwertera",
                  `${formatNumber(simulation.inverter_loss_mwh, 3)} MWh (${formatPercent(simulation.inverter_loss_fraction)})`,
                ],
              ] as [string, ReactNode][])
            : []),
        ]}
      />
      {simulation ? (
        <ProfileChart
          title={`Produkcja AC instalacji PV (${simulation.simulator})`}
          timestamps={simulation.ac_profile.timestamps}
          series={[{ name: "Produkcja AC", values: simulation.ac_profile.power_mw, color: SERIES_1 }]}
          unit="MW"
        />
      ) : (
        <p className="muted">
          {solar.module_count === 0
            ? "Na dostępnym obszarze nie zmieścił się żaden moduł."
            : "Bez szeregu nasłonecznienia — produkcja nie została policzona."}
        </p>
      )}
    </div>
  );
}

const SOURCE_LABELS: Record<string, string> = { wind: "wiatr", solar: "PV" };

function HybridResultView({ hybrid }: { hybrid: HybridResult }) {
  return (
    <div className="technology-result">
      <h3>Wynik: {hybrid.sources.map((source) => SOURCE_LABELS[source] ?? source).join(" + ")}</h3>
      <StatTable
        rows={[
          ["Limit przyłącza", `${formatNumber(hybrid.grid_connection_limit_mw, 2)} MW`],
          ["Produkcja łączna", `${formatNumber(hybrid.aggregate_energy_mwh, 2)} MWh`],
          ["Dostarczone do sieci", `${formatNumber(hybrid.delivered_energy_mwh, 2)} MWh`],
          [
            "Curtailment",
            `${formatNumber(hybrid.curtailed_energy_mwh, 2)} MWh (${formatPercent(hybrid.curtailed_energy_fraction)})`,
          ],
          ["Wykorzystanie przyłącza", formatPercent(hybrid.utilization_fraction)],
        ]}
      />
      <ProfileChart
        title="Produkcja łączna i dostawa do sieci"
        timestamps={hybrid.aggregate_profile.timestamps}
        series={[
          { name: "Produkcja łączna", values: hybrid.aggregate_profile.power_mw, color: SERIES_1 },
          { name: "Dostarczone do sieci", values: hybrid.delivered_profile.power_mw, color: SERIES_2 },
        ]}
        reference={{ label: "Limit przyłącza", value: hybrid.grid_connection_limit_mw }}
        unit="MW"
      />
    </div>
  );
}

function BatteryResultView({ battery, hybrid }: { battery: BatteryResult; hybrid: HybridResult | null }) {
  return (
    <div className="technology-result">
      <h3>
        Wynik: {battery.battery_manufacturer} {battery.battery_model}
      </h3>
      <StatTable
        rows={[
          ["Naładowano", `${formatNumber(battery.charged_energy_mwh, 2)} MWh`],
          ["Rozładowano", `${formatNumber(battery.discharged_energy_mwh, 2)} MWh`],
          ["Straty magazynu", `${formatNumber(battery.round_trip_loss_mwh, 2)} MWh`],
          [
            "Curtailment z magazynem",
            hybrid
              ? `${formatNumber(battery.curtailed_energy_mwh, 2)} MWh (bez magazynu: ${formatNumber(hybrid.curtailed_energy_mwh, 2)} MWh)`
              : `${formatNumber(battery.curtailed_energy_mwh, 2)} MWh`,
          ],
          ["Początkowy stan naładowania", formatPercent(battery.initial_state_of_charge_fraction)],
          ["Końcowy stan naładowania", formatPercent(battery.final_state_of_charge_fraction)],
        ]}
      />
      <ProfileChart
        title="Dostawa do sieci z magazynem i bez"
        timestamps={battery.delivered_profile.timestamps}
        series={[
          ...(hybrid
            ? [{ name: "Bez magazynu", values: hybrid.delivered_profile.power_mw, color: SERIES_1 }]
            : []),
          { name: "Z magazynem", values: battery.delivered_profile.power_mw, color: SERIES_2 },
        ]}
        reference={{ label: "Moc docelowa", value: battery.target_power_mw }}
        unit="MW"
      />
      <ProfileChart
        title="Stan naładowania magazynu"
        timestamps={battery.delivered_profile.timestamps}
        series={[
          {
            name: "Stan naładowania",
            values: battery.state_of_charge_fraction.map((fraction) => fraction * 100),
            color: SERIES_1,
          },
        ]}
        unit="%"
        digits={1}
      />
    </div>
  );
}

export default function TechnologyResultsPage() {
  const { screeningId } = useParams<{ screeningId: string }>();
  const [summary, setSummary] = useState<ScreeningSummary | null>(null);
  const [results, setResults] = useState<TechnologyResults | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (!screeningId) return;
    try {
      const [screening, technologies] = await Promise.all([
        getScreening(screeningId),
        getTechnologyResults(screeningId),
      ]);
      setSummary(screening);
      setResults(technologies);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Nie udało się pobrać wyników technologii.");
    }
  }, [screeningId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  if (!screeningId) return <p>Brak identyfikatora screeningu.</p>;
  if (error) return <p className="form-error">{error}</p>;
  if (!summary || !results) return <p>Ładowanie…</p>;

  const backLink = <Link to={`/screenings/${screeningId}`}>← Szczegóły analizy</Link>;
  if (summary.status !== "completed") {
    return (
      <section>
        <p>{backLink}</p>
        <h1>Wyniki technologii</h1>
        <p>
          <StatusBadge status={summary.status} /> Obliczenia technologii wymagają zakończonego screeningu.
        </p>
      </section>
    );
  }

  const { wind, solar, hybrid, battery } = results;
  const hasProduction = Boolean(wind?.simulation || solar?.simulation);
  const onSaved = () => void reload();

  return (
    <section>
      <p>{backLink}</p>
      <h1>Wyniki technologii</h1>
      <p className="muted">
        {summary.technology} / {summary.country} — dostępna powierzchnia{" "}
        {formatNumber(summary.available_area_square_meters)} m². Ponowne obliczenie wiatru lub PV
        usuwa wyniki hybrydy i magazynu, a ponowna hybryda — wynik magazynu.
      </p>

      <TechnologySection
        title="Wiatr"
        description="Rozmieszczenie turbin na dostępnym obszarze i, z szeregiem wiatrowym, symulacja produkcji."
        submitLabel={wind ? "Przelicz wiatr" : "Rozmieść turbiny"}
        submit={(fields) => createTurbineLayout(screeningId, fields)}
        onSaved={onSaved}
        fields={
          <>
            <Field label="Katalog turbin (YAML/JSON)">
              <input type="file" name="turbine_catalog" accept=".yaml,.yml,.json" required />
            </Field>
            <Field label="Odstęp [średnice wirnika]">
              <input type="number" name="spacing_rotor_diameters" min={0} step="any" defaultValue={5} required />
            </Field>
            <Field label="Krok siatki [m] (opcjonalnie)">
              <input type="number" name="grid_spacing_m" min={0} step="any" />
            </Field>
            <CatalogModelFields prefix="turbine" />
            <Field label="Szereg wiatrowy (opcjonalnie)">
              <input type="file" name="wind_resource" accept=".yaml,.yml,.json" />
            </Field>
            <SimulationFactorFields />
            <label className="checkbox-field">
              <input type="checkbox" name="use_pywake" value="true" /> Model wake PyWake
            </label>
          </>
        }
      >
        {wind && <WindResultView wind={wind} />}
      </TechnologySection>

      <TechnologySection
        title="Fotowoltaika"
        description="Wymiarowanie instalacji PV na dostępnym obszarze i, z szeregiem nasłonecznienia, symulacja produkcji."
        submitLabel={solar ? "Przelicz PV" : "Zwymiaruj instalację"}
        submit={(fields) => createSolarArray(screeningId, fields)}
        onSaved={onSaved}
        fields={
          <>
            <Field label="Katalog modułów (YAML/JSON)">
              <input type="file" name="solar_catalog" accept=".yaml,.yml,.json" required />
            </Field>
            <Field label="Współczynnik zabudowy GCR (0–1]">
              <input
                type="number"
                name="ground_coverage_ratio"
                min={0}
                max={1}
                step="any"
                defaultValue={0.4}
                required
              />
            </Field>
            <CatalogModelFields prefix="solar" />
            <Field label="Szereg nasłonecznienia (opcjonalnie)">
              <input type="file" name="solar_resource" accept=".yaml,.yml,.json" />
            </Field>
            <SimulationFactorFields />
            <label className="checkbox-field">
              <input type="checkbox" name="use_pvlib" value="true" /> Model inwertera pvlib
            </label>
          </>
        }
      >
        {solar && <SolarResultView solar={solar} />}
      </TechnologySection>

      <TechnologySection
        title="Hybryda i przyłącze"
        description="Suma produkcji wiatru i PV ograniczona do mocy przyłącza (curtailment)."
        disabledReason={
          hasProduction
            ? null
            : "Najpierw policz produkcję wiatru lub PV (z plikiem szeregu czasowego)."
        }
        submitLabel={hybrid ? "Przelicz hybrydę" : "Policz hybrydę"}
        submit={(fields) => createHybrid(screeningId, fields)}
        onSaved={onSaved}
        fields={
          <Field label="Limit przyłącza [MW]">
            <input type="number" name="grid_connection_limit_mw" min={0} step="any" required />
          </Field>
        }
      >
        {hybrid && <HybridResultView hybrid={hybrid} />}
      </TechnologySection>

      <TechnologySection
        title="Magazyn energii"
        description="Ładowanie nadwyżką ponad limit przyłącza i rozładowanie, gdy produkcja jest poniżej limitu."
        disabledReason={hybrid ? null : "Najpierw policz hybrydę — magazyn pracuje na jej profilu."}
        submitLabel={battery ? "Przelicz magazyn" : "Policz magazyn"}
        submit={(fields) => createBatteryDispatch(screeningId, fields)}
        onSaved={onSaved}
        fields={
          <>
            <Field label="Katalog magazynów (YAML/JSON)">
              <input type="file" name="battery_catalog" accept=".yaml,.yml,.json" required />
            </Field>
            <CatalogModelFields prefix="battery" />
            <Field label="Początkowy stan naładowania (0–1, opcjonalnie)">
              <input type="number" name="initial_state_of_charge_fraction" min={0} max={1} step="any" />
            </Field>
          </>
        }
      >
        {battery && <BatteryResultView battery={battery} hybrid={hybrid ?? null} />}
      </TechnologySection>
    </section>
  );
}
