const LABELS: Record<string, string> = {
  pending: "Oczekuje",
  running: "W trakcie",
  completed: "Zakończono",
  failed: "Błąd",
};

export default function StatusBadge({ status }: { status: string }) {
  const label = LABELS[status] ?? status;
  return <span className={`status-badge status-badge--${status}`}>{label}</span>;
}
