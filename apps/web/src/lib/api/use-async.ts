"use client";

import { useCallback, useEffect, useState } from "react";

export type AsyncStatus = "loading" | "ok" | "empty" | "error";

type State<T> = { status: AsyncStatus; data?: T };

/**
 * Runs an async loader and tracks loading / ok / empty / error.
 * Pass a stable loader (module-level function). Swap fixtures for real
 * fetch calls without touching consumers.
 */
export function useAsync<T>(load: () => Promise<T>): {
  status: AsyncStatus;
  data: T | undefined;
  retry: () => void;
} {
  const [nonce, setNonce] = useState(0);
  const [state, setState] = useState<State<T>>({ status: "loading" });

  useEffect(() => {
    let alive = true;
    load()
      .then((data) => {
        if (!alive) return;
        const empty = Array.isArray(data) && data.length === 0;
        setState({ status: empty ? "empty" : "ok", data });
      })
      .catch(() => {
        if (alive) setState({ status: "error" });
      });
    return () => {
      alive = false;
    };
  }, [load, nonce]);

  const retry = useCallback(() => {
    setState({ status: "loading" });
    setNonce((n) => n + 1);
  }, []);

  return { status: state.status, data: state.data, retry };
}
