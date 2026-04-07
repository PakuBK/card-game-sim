import {
  Card,
  CardHeader,
  CardTitle,
  CardAction,
  CardContent,
  CardFooter,
} from "@/components/ui/card";

export default function SimulatorPage() {
  return (
    <main className="min-h-screen p-6">
      <section className="px-4 flex flex-col gap-8">
        <Card>
          <CardHeader className="border-b border-border">
            <CardTitle>Board #1</CardTitle>
          </CardHeader>
          <CardContent>
            <p>Card Content</p>
          </CardContent>
          <CardFooter className="border-t border-border">
            <p>Board Options</p>
          </CardFooter>
        </Card>
        <Card>
          <CardHeader className="border-b border-border">
            <CardTitle>Board #2</CardTitle>
            <CardAction>Card Action</CardAction>
          </CardHeader>
          <CardContent>
            <p>Card Content</p>
          </CardContent>
          <CardFooter className="border-t border-border">
            <p>Board Options</p>
          </CardFooter>
        </Card>
      </section>
    </main>
  );
}
