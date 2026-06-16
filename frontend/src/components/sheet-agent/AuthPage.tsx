/**
 * AuthPage.tsx — Login / Register page
 *
 * Matches your existing orange-amber UI theme exactly.
 * Tabs: "Sign In" | "Create Account"
 * On success → calls onAuth(user) which the parent uses to set auth state.
 */
import { useState } from "react";
import { Eye, EyeOff, Loader2, FileSpreadsheet, Sparkles } from "lucide-react";
import { login, register, type User } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface AuthPageProps {
  onAuth: (user: User) => void;
}

type Tab = "login" | "register";

export function AuthPage({ onAuth }: AuthPageProps) {
  const [tab,       setTab]       = useState<Tab>("login");
  const [fullName,  setFullName]  = useState("");
  const [email,     setEmail]     = useState("");
  const [password,  setPassword]  = useState("");
  const [confirm,   setConfirm]   = useState("");
  const [showPw,    setShowPw]    = useState(false);
  const [loading,   setLoading]   = useState(false);
  const [error,     setError]     = useState("");

  const hour = new Date().getHours();
  const greeting =
    hour < 12 ? "Good morning" :
    hour < 18 ? "Good afternoon" :
                "Good evening";

  function resetForm() {
    setFullName(""); setEmail(""); setPassword(""); setConfirm(""); setError("");
  }

  function switchTab(t: Tab) {
    setTab(t);
    resetForm();
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    if (tab === "register") {
      if (!fullName.trim()) { setError("Full name is required."); return; }
      if (password !== confirm) { setError("Passwords do not match."); return; }
      if (password.length < 6) { setError("Password must be at least 6 characters."); return; }
    }

    setLoading(true);
    try {
      const res = tab === "login"
        ? await login(email, password)
        : await register(fullName, email, password);
      onAuth(res.user);
    } catch (err: unknown) {
      const e = err as { message?: string };
      setError(e?.message ?? "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-background px-4">

      {/* Background decoration */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -top-40 -right-40 h-96 w-96 rounded-full bg-primary/5 blur-3xl" />
        <div className="absolute -bottom-40 -left-40 h-96 w-96 rounded-full bg-primary/5 blur-3xl" />
      </div>

      <div className="relative w-full max-w-md">

        {/* Logo + greeting */}
        <div className="mb-8 text-center">
          <div className="mb-4 flex items-center justify-center gap-2">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 border border-primary/20">
              <FileSpreadsheet className="h-5 w-5 text-primary" />
            </div>
            <span className="text-xl font-semibold text-foreground">SheetAgent AI</span>
          </div>
          <h1 className="font-serif text-3xl font-normal text-foreground">
            ✦ {greeting}
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            {tab === "login"
              ? "Sign in to continue building sheets"
              : "Create your account to get started"}
          </p>
        </div>

        {/* Card */}
        <div className="rounded-2xl border border-border bg-card shadow-lg shadow-black/5">

          {/* Tabs */}
          <div className="flex border-b border-border">
            {(["login", "register"] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => switchTab(t)}
                className={cn(
                  "flex-1 py-3 text-sm font-medium transition-colors",
                  tab === t
                    ? "border-b-2 border-primary text-primary"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {t === "login" ? "Sign In" : "Create Account"}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="space-y-4 p-6">

            {/* Full name (register only) */}
            {tab === "register" && (
              <div className="space-y-1.5">
                <Label htmlFor="fullName">Full Name</Label>
                <Input
                  id="fullName"
                  type="text"
                  placeholder="Muhammad Raza"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  required
                  autoFocus
                  className="h-10"
                />
              </div>
            )}

            {/* Email */}
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoFocus={tab === "login"}
                className="h-10"
              />
            </div>

            {/* Password */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label htmlFor="password">Password</Label>
                {tab === "login" && (
                  <button
                    type="button"
                    className="text-xs text-primary hover:underline"
                    onClick={() => setError("Password reset: contact support.")}
                  >
                    Forgot password?
                  </button>
                )}
              </div>
              <div className="relative">
                <Input
                  id="password"
                  type={showPw ? "text" : "password"}
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="h-10 pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPw((p) => !p)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {/* Confirm password (register only) */}
            {tab === "register" && (
              <div className="space-y-1.5">
                <Label htmlFor="confirm">Confirm Password</Label>
                <div className="relative">
                  <Input
                    id="confirm"
                    type={showPw ? "text" : "password"}
                    placeholder="••••••••"
                    value={confirm}
                    onChange={(e) => setConfirm(e.target.value)}
                    required
                    className="h-10 pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPw((p) => !p)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>
            )}

            {/* Error */}
            {error && (
              <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {error}
              </div>
            )}

            {/* Submit */}
            <Button type="submit" disabled={loading} className="h-10 w-full font-semibold">
              {loading ? (
                <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Please wait…</>
              ) : tab === "login" ? (
                "Sign In"
              ) : (
                "Create Account"
              )}
            </Button>

            {/* Register features hint */}
            {tab === "register" && (
              <div className="grid grid-cols-3 gap-2 pt-1">
                {[
                  "AI Excel builder",
                  "PDF & image OCR",
                  "Charts & dashboards",
                ].map((f) => (
                  <div
                    key={f}
                    className="flex items-center gap-1 rounded-lg border border-border bg-muted/50 px-2 py-1.5 text-center text-[11px] text-muted-foreground"
                  >
                    <Sparkles className="h-2.5 w-2.5 shrink-0 text-primary" />
                    {f}
                  </div>
                ))}
              </div>
            )}
          </form>

          {/* Switch tab link */}
          <div className="border-t border-border px-6 py-4 text-center text-sm text-muted-foreground">
            {tab === "login" ? (
              <>Don't have an account?{" "}
                <button onClick={() => switchTab("register")}
                  className="font-medium text-primary hover:underline">
                  Create one
                </button>
              </>
            ) : (
              <>Already have an account?{" "}
                <button onClick={() => switchTab("login")}
                  className="font-medium text-primary hover:underline">
                  Sign in
                </button>
              </>
            )}
          </div>
        </div>

        <p className="mt-6 text-center text-[11px] text-muted-foreground">
          By continuing you agree to our Terms of Service & Privacy Policy.
        </p>
      </div>
    </div>
  );
}
