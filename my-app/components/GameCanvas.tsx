"use client";

import{ useEffect, useRef } from "react";

export default function GameCanvas() {
    const canvasRef = useRef<HTMLCanvasElement | null>(null);

    useEffect(() => {
        const canvas = canvasRef.current;
        if(!canvas) return;

        const ctx = canvas.getContext("2d");
        if(!ctx) return;

        ctx.fillStyle = "white";
        ctx.fillRect(50,50,100,100);
    },[]);

    return (
        <canvas
            ref={canvasRef}
            width={300}
            height={200}
            className="border border-zinc-700"
        />
    );
}