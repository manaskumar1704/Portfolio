"use client";

import { useState } from "react";
import GameCanvas from "./GameCanvas";

export default function GamePanel() {
  const [visible, setVisible] = useState<boolean>(true);

  return (
    <div
      className="hidden md:static md:mt-12 lg:fixed lg:right-6 lg:z-50"
      style={{ top: "calc(var(--navbar-height) + 2rem)" }}
    >
      {/* Toggle Button */}
      <button
        onClick={() => setVisible(!visible)}
        className="mb-2 w-80 bg-white text-black px-4 py-2 rounded-md text-sm text-center transition-all duration-200"
      >
        {visible ? "Hide Game" : "Show Game"}
      </button>

      {/* Game Window */}
      {visible && (
        <div className="w-80 bg-zinc-900 border border-zinc-700 rounded-xl p-4 space-y-4">
          <h3 className="text-lg font-semibold">Mini Game</h3>

          <GameCanvas />

          <button className="w-full bg-white text-black py-2 rounded-md text-sm">
            Play Again
          </button>
        </div>
      )}
    </div>
  );
}
