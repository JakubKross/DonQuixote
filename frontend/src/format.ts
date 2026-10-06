const numberFormats = new Map<number, Intl.NumberFormat>();

export function formatNumber(value: number | null | undefined, digits = 1): string {
  if (value == null) return "—";
  let format = numberFormats.get(digits);
  if (!format) {
    format = new Intl.NumberFormat("pl-PL", {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });
    numberFormats.set(digits, format);
  }
  return format.format(value);
}

export function formatPercent(fraction: number | null | undefined, digits = 1): string {
  return fraction == null ? "—" : `${formatNumber(fraction * 100, digits)}%`;
}

const dateTimeFormat = new Intl.DateTimeFormat("pl-PL", {
  dateStyle: "short",
  timeStyle: "short",
});

export function formatDateTime(value: string | null | undefined): string {
  return value ? dateTimeFormat.format(new Date(value)) : "—";
}
