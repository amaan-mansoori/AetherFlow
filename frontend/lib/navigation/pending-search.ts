let pendingJobSearch: string | null = null;

export function setPendingJobSearch(value: string): void {
  pendingJobSearch = value;
}

export function takePendingJobSearch(): string | null {
  const value = pendingJobSearch;
  pendingJobSearch = null;
  return value;
}
