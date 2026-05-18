import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export const fmt = (n: number) => Math.round(n || 0).toLocaleString('en-PK');
export const fmtPKR = (n: number) => 'PKR ' + fmt(n);
export const fmtAmount = (n: number, currency = 'PKR') => `${currency} ${fmt(n)}`;
