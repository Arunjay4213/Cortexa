"use client";

import { useState, useEffect, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/providers/AuthProvider";
import { Brain, ArrowRight, Key, AlertCircle } from "lucide-react";

export default function LoginPage() {
  const { isAuthenticated, login } = useAuth();
  const router = useRouter();
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // Already authenticated — redirect
  useEffect(() => {
    if (isAuthenticated) {
      router.replace("/overview");
    }
  }, [isAuthenticated, router]);

  if (isAuthenticated) {
    return null;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = apiKey.trim();
    if (!trimmed) return;

    setLoading(true);
    setError("");

    try {
      await login(trimmed);
      router.replace("/overview");
    } catch {
      setError("Invalid API key. Check your key and try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className="min-h-screen flex items-center justify-center px-4"
      style={{ background: "var(--dashboard-bg)" }}
    >
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="flex items-center justify-center gap-2.5 mb-8">
          <Brain
            className="w-7 h-7"
            style={{ color: "var(--grafana-green)" }}
          />
          <span
            className="font-mono font-bold text-lg tracking-tight"
            style={{ color: "var(--grafana-text-primary)" }}
          >
            CORTEXA
          </span>
        </div>

        {/* Card */}
        <div
          className="rounded-lg border p-6"
          style={{
            background: "var(--panel-bg)",
            borderColor: "var(--panel-border)",
          }}
        >
          <h1
            className="text-base font-semibold mb-1"
            style={{ color: "var(--grafana-text-primary)" }}
          >
            Connect to Dashboard
          </h1>
          <p
            className="text-sm mb-5"
            style={{ color: "var(--grafana-text-secondary)" }}
          >
            Enter your API key to access the memory observability dashboard.
          </p>

          <form onSubmit={handleSubmit}>
            <label
              className="block text-xs font-medium mb-1.5"
              style={{ color: "var(--grafana-text-secondary)" }}
            >
              API Key
            </label>
            <div className="relative mb-4">
              <Key
                className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4"
                style={{ color: "var(--grafana-text-muted)" }}
              />
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="cx_..."
                autoFocus
                disabled={loading}
                className="w-full pl-9 pr-3 py-2 rounded text-sm font-mono border outline-none transition-colors disabled:opacity-50"
                style={{
                  background: "var(--dashboard-bg)",
                  borderColor: error
                    ? "var(--grafana-red)"
                    : "var(--panel-border)",
                  color: "var(--grafana-text-primary)",
                }}
              />
            </div>

            {error && (
              <div
                className="flex items-center gap-2 text-xs mb-4 p-2.5 rounded border"
                style={{
                  color: "var(--grafana-red)",
                  background: "rgba(242, 73, 92, 0.08)",
                  borderColor: "rgba(242, 73, 92, 0.2)",
                }}
              >
                <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !apiKey.trim()}
              className="w-full flex items-center justify-center gap-2 py-2 px-4 rounded text-sm font-medium transition-opacity disabled:opacity-50"
              style={{
                background: "var(--grafana-green)",
                color: "#111217",
              }}
            >
              {loading ? "Validating..." : "Connect"}
              {!loading && <ArrowRight className="w-4 h-4" />}
            </button>
          </form>
        </div>

        <p
          className="text-center text-xs mt-4"
          style={{ color: "var(--grafana-text-muted)" }}
        >
          Use your <code className="font-mono">cx_</code> API key or admin
          secret
        </p>
      </div>
    </div>
  );
}
