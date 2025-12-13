"use client";

import { useState} from "react";

export default function GamePanel() {
  const [visible, setVisible] = useState(true);

  return (
    <>
    {/* Toggle Button */}
    <button
      onClick={() => setVisible(!visible)}
      className="fixed top-6 right-6 bg-white text-black px-4 py-2 rounded-md text-sm"
    >
      {visible ? "Hide Game Panel" : "Show Game Panel"}
    </button>
    
    {/* Game Panel */}
    {visible && (
      <div className="fixed top-16 right-6 w-80 h-96 bg-zinc-900 border border-zinc-700 rounded-x1 p-4">
        <h3 className="text-lg font-semibold mb-2">
          Mini Game
        </h3>

        <div className="h-48 bg-black border border-zinc-700 rounded-md flex items-center justify-center text-gray-500">
          Game goes here
        </div>

        <button className="mt-4 w-full bg-white text-black py-2 rounded-md text-sm">
          Play Again
        </button>
      </div>
    )}
    </>
  );
}