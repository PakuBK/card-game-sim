import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/debug")({
  component: DebugPage,
});

function DebugPage() {
  return (
    <div className="min-h-screen p-6">
      <div className="mx-auto w-full max-w-3xl">
        <h1 className="text-2xl font-semibold">Debug</h1>
        <p className="mt-2 text-sm opacity-80">Debug tools will go here.</p>
      </div>
    </div>
  );
}
