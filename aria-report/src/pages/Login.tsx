import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  async function submit(event: React.FormEvent) {
    event.preventDefault(); setPending(true); setError("");
    try { await api.auth.login(email, password); navigate("/"); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Sign in failed"); }
    finally { setPending(false); }
  }
  return <main className="min-h-screen grid place-items-center p-6 bg-aria-bg"><form onSubmit={submit} className="glass w-full max-w-md rounded-xl p-7 space-y-5"><div><p className="text-2xl font-semibold text-aria-text1">ARIA</p><p className="text-sm text-aria-text4 mt-1">Sign in to your research workspace.</p></div><div className="space-y-2"><Label htmlFor="email">Work email</Label><Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></div><div className="space-y-2"><Label htmlFor="password">Password</Label><Input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required /></div>{error && <p className="text-sm text-red-400">{error}</p>}<Button className="w-full" type="submit" disabled={pending}>{pending ? "Signing in..." : "Sign in"}</Button></form></main>;
}
