export type HealthResponse = {
  status: string;
  now: string;
};

export type CardSummary = {
  id: string;
  name: string;
  cost: number;
};

export type EchoRequest = {
  message: string;
  payload?: Record<string, unknown> | null;
};

export type EchoResponse = {
  received: EchoRequest;
};
