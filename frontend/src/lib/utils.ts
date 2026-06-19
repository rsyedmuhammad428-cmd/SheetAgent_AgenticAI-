import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Returns a contextual greeting based on the current hour in Pakistan
 * Standard Time (Asia/Karachi, UTC+5). Uses built-in Intl — no library needed.
 *
 *  12 AM – 4:59 AM  →  Good night
 *   5 AM – 11:59 AM  →  Good morning
 *  12 PM –  4:59 PM  →  Good afternoon
 *   5 PM –  8:59 PM  →  Good evening
 *   9 PM – 11:59 PM  →  Good night
 */
export function getPakistanGreeting(): string {
  const hour = Number(
    new Intl.DateTimeFormat("en-US", {
      timeZone: "Asia/Karachi",
      hour: "numeric",
      hour12: false,
    }).format(new Date()),
  );
  if (hour >= 5  && hour < 12) return "Good morning";
  if (hour >= 12 && hour < 17) return "Good afternoon";
  if (hour >= 17 && hour < 21) return "Good evening";
  return "Good night";
}
