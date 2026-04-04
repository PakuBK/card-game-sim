import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { z } from "zod";

import { getCards, getHealth, postEcho } from "../../api/endpoints";

const EchoMessageSchema = z
  .string()
  .trim()
  .min(1, "Message is required")
  .max(200, "Message must be at most 200 characters");

function formatIso(iso: string | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

export default function DebugPage() {
  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 30_000,
  });

  const cardsQuery = useQuery({
    queryKey: ["cards"],
    queryFn: getCards,
  });

  const [echoMessage, setEchoMessage] = useState("hello from frontend");
  const [echoValidationError, setEchoValidationError] = useState<string | null>(null);

  const echoMutation = useMutation({
    mutationFn: async () =>
      postEcho({
        message: echoMessage,
        payload: { at: new Date().toISOString() },
      }),
  });

  const healthText = useMemo(() => {
    if (healthQuery.isPending) return "loading";
    if (healthQuery.isError) return `error: ${healthQuery.error.message}`;
    return `${healthQuery.data.status} (${formatIso(healthQuery.data.now)})`;
  }, [healthQuery.data, healthQuery.error, healthQuery.isError, healthQuery.isPending]);

  return (
    <div className="min-h-screen p-6">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
        <header className="flex flex-col gap-2">
          <h1 className="text-2xl font-semibold">Card Game Sim</h1>
          <p className="text-sm opacity-80">
            Minimal React UI wired to the dummy FastAPI backend (via Vite proxy).
          </p>
        </header>

        <section className="rounded-md border p-4">
          <div className="flex items-center justify-between gap-4">
            <h2 className="text-lg font-medium">Backend</h2>
            <button
              type="button"
              className="rounded border px-3 py-2 text-sm"
              onClick={() => void healthQuery.refetch()}
            >
              Refresh
            </button>
          </div>
          <div className="mt-3 text-sm">
            <div>
              <span className="font-medium">Health:</span> <span>{healthText}</span>
            </div>
          </div>
        </section>

        <section className="rounded-md border p-4">
          <h2 className="text-lg font-medium">Cards</h2>
          <div className="mt-3">
            {cardsQuery.isPending ? (
              <div className="text-sm">loading…</div>
            ) : cardsQuery.isError ? (
              <div className="text-sm">error: {cardsQuery.error.message}</div>
            ) : (
              <ul className="flex flex-col gap-2">
                {cardsQuery.data.map((c) => (
                  <li
                    key={c.id}
                    className="flex items-center justify-between rounded border px-3 py-2"
                  >
                    <div className="flex flex-col">
                      <span className="font-medium">{c.name}</span>
                      <span className="text-xs opacity-70">id: {c.id}</span>
                    </div>
                    <div className="text-sm">cost: {c.cost}</div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>

        <section className="rounded-md border p-4">
          <h2 className="text-lg font-medium">Echo</h2>
          <div className="mt-3 flex flex-col gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-sm font-medium">Message</span>
              <input
                className="rounded border px-3 py-2"
                value={echoMessage}
                onChange={(e) => {
                  setEchoMessage(e.target.value);
                  setEchoValidationError(null);
                }}
              />
              {echoValidationError ? (
                <span className="text-sm text-red-600">{echoValidationError}</span>
              ) : null}
            </label>

            <div className="flex items-center gap-3">
              <button
                type="button"
                className="rounded border px-3 py-2 text-sm"
                onClick={() => {
                  const parsed = EchoMessageSchema.safeParse(echoMessage);
                  if (!parsed.success) {
                    setEchoValidationError(parsed.error.issues[0]?.message ?? "Invalid message");
                    return;
                  }

                  setEchoValidationError(null);
                  echoMutation.mutate();
                }}
                disabled={echoMutation.isPending}
              >
                {echoMutation.isPending ? "Sending…" : "Send"}
              </button>
              {echoMutation.isError ? (
                <span className="text-sm">error: {echoMutation.error.message}</span>
              ) : null}
              {echoMutation.isSuccess ? <span className="text-sm">ok</span> : null}
            </div>

            <div className="rounded border p-3">
              <div className="text-xs font-medium opacity-70">Response</div>
              <pre className="mt-2 overflow-auto text-xs">
                {echoMutation.data ? JSON.stringify(echoMutation.data, null, 2) : "(none)"}
              </pre>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
