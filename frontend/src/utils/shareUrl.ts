export function shareUrl(token: string): string {
  return `${window.location.origin}${import.meta.env.BASE_URL}tree?share=${token}`;
}
