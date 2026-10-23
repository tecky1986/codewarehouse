export interface ApiEnvelope<T> {
  code: number | string;
  message: string;
  data: T;
}

export function isOk<T>(body: ApiEnvelope<T>): boolean {
  return body.code === 0;
}
