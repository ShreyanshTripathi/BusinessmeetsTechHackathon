export const hhmm = (iso: string | null | undefined) => (iso ? iso.slice(11, 16) : "--:--");

/** Parse a timezone-less plant ISO string into minutes since epoch, treating it as UTC so no conversion happens. */
function toMin(iso: string): number {
  return Date.parse(iso.slice(0, 19) + "Z") / 60000;
}
export function minutesBetween(from: string, clock: string): number {
  return Math.max(0, Math.round(toMin(clock) - toMin(from)));
}
