import GamePanel from "../components/GamePanel";

export default function HomePage() {
  return (
    <main className="min-h-screen bg-black text-white p-8">
      <h1 className="text-4xl font-bold"> Hi, I'm Manas </h1>

      {/* other sections here */}

      <GamePanel />
    </main>
  );
}