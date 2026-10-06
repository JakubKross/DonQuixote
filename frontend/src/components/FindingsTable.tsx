import type { FindingSummary } from "../api/client";

export default function FindingsTable({ findings }: { findings: FindingSummary[] }) {
  if (findings.length === 0) {
    return <p>Brak findingów.</p>;
  }

  return (
    <table className="findings-table">
      <thead>
        <tr>
          <th>Poziom</th>
          <th>Status</th>
          <th>Wiadomość</th>
          <th>Źródło</th>
        </tr>
      </thead>
      <tbody>
        {findings.map((finding) => (
          <tr key={finding.id} className={`finding-row finding-row--${finding.level}`}>
            <td>{finding.level}</td>
            <td>{finding.status}</td>
            <td>{finding.message}</td>
            <td>
              {finding.data_source} ({finding.data_version})
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
