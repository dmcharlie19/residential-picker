export interface Complex { id: number; name: string; city: string; developer: string | null; district: string | null; housing_class: string | null; completion_status: string; completion_description: string | null; completion_source_url: string | null }
export interface Match { complex: Complex; match_type: 'lot' | 'estimate'; lot: null | { id: number; rooms: number; area_m2: string; starting_price_rub: string; updated_at: string; source_url: string | null; building: string | null; is_demo: boolean }; matched_area_m2: string; estimated_price_rub: string; price_source_url: string | null; price_observed_on: string; warnings: string[] }
export interface SearchResult { query: { city: string; budget_rub: string; rooms: number[] }; generated_at: string; demo_mode: boolean; count: number; results: Match[]; warnings: string[] }
export type Fields = Partial<Record<'city' | 'budget' | 'rooms', string[]>>;
export class ApiError extends Error { constructor(message: string, public fields: Fields = {}) { super(message); } }
export async function search(city: string, budget: string, rooms: number[], signal: AbortSignal): Promise<SearchResult> {
  const params = new URLSearchParams({ city, budget });
  rooms.forEach(room => params.append('rooms', String(room)));
  const response = await fetch(`${import.meta.env.BASE_URL}api/v1/search?${params}`, { signal });
  if (!response.ok) { let fields: Fields = {}; if (response.status === 422) { try { fields = (await response.json()).error?.fields || {}; } catch { /* Use a safe message for invalid server responses. */ } } throw new ApiError(response.status === 422 ? 'Проверьте параметры поиска' : 'Не удалось выполнить поиск. Попробуйте ещё раз.', fields); }
  return response.json();
}
export function normalize(value: string, integerDigits: number): string | null {
  const normalized = value.replace(/[\s\u00a0\u202f]/g, '').replace(',', '.');
  if (!/^\d+(?:\.\d{1,2})?$/.test(normalized)) return null;
  const [whole, fraction = ''] = normalized.split('.');
  const clean = whole.replace(/^0+(?=\d)/, '');
  if (clean.length > integerDigits || /^0*$/.test(clean + fraction)) return null;
  return clean + (fraction ? `.${fraction}` : '');
}
// Work directly with decimal strings so large amounts retain every kopeck.
export function decimal(value: string): string { const [whole, fraction] = value.split('.'); return whole.replace(/\B(?=(\d{3})+(?!\d))/g, '\u00a0') + (fraction ? `,${fraction}` : ''); }
export function safeUrl(value: string | null): string | undefined { if (!value) return; try { const url = new URL(value); if (url.protocol === 'http:' || url.protocol === 'https:') return url.href; } catch { /* Invalid source URLs are not links. */ } }
