import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { UserPlus, ShieldCheck, UserX } from "lucide-react";
import { toast } from "sonner";
import { PageTopbar } from "@/components/layout/PageTopbar";
import { GlassCard } from "@/components/glass/GlassCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, type OrganizationRole } from "@/lib/api";

const ROLES: Array<{ value: OrganizationRole; label: string; description: string }> = [
  { value: "admin", label: "Admin", description: "Manage members and organization settings." },
  { value: "member", label: "Member", description: "Run research and approve findings." },
  { value: "viewer", label: "Viewer", description: "Read research evidence and reports only." },
];

function eventLabel(eventType: string) {
  return eventType.replaceAll(".", " ").replaceAll("_", " ");
}

export default function Organization() {
  const client = useQueryClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<OrganizationRole>("member");
  const [resettingUserId, setResettingUserId] = useState<string | null>(null);
  const [replacementPassword, setReplacementPassword] = useState("");
  const users = useQuery({ queryKey: ["organization", "users"], queryFn: api.organization.users });
  const audit = useQuery({ queryKey: ["organization", "audit"], queryFn: api.organization.auditEvents });
  const refresh = () => {
    client.invalidateQueries({ queryKey: ["organization", "users"] });
    client.invalidateQueries({ queryKey: ["organization", "audit"] });
  };
  const createUser = useMutation({
    mutationFn: () => api.organization.createUser(email, password, role),
    onSuccess: () => { setEmail(""); setPassword(""); setRole("member"); refresh(); toast.success("Member added"); },
    onError: (error: Error) => toast.error(error.message),
  });
  const updateUser = useMutation({
    mutationFn: ({ userId, updates }: { userId: string; updates: { role?: OrganizationRole; disabled?: boolean } }) => api.organization.updateUser(userId, updates),
    onSuccess: () => { refresh(); toast.success("Member access updated"); },
    onError: (error: Error) => toast.error(error.message),
  });
  const resetPassword = useMutation({
    mutationFn: ({ userId, password }: { userId: string; password: string }) => api.organization.resetUserPassword(userId, password),
    onSuccess: () => { setResettingUserId(null); setReplacementPassword(""); refresh(); toast.success("Temporary password set. The member must sign in again."); },
    onError: (error: Error) => toast.error(error.message),
  });

  return <div className="flex h-full flex-col overflow-hidden">
    <PageTopbar title="Organization" />
    <div className="flex-1 overflow-y-auto p-5 pb-20 md:pb-5 max-w-5xl w-full mx-auto space-y-5">
      <GlassCard className="p-5">
        <div className="flex items-start gap-3 mb-5">
          <div className="mt-0.5 rounded-lg border border-aria-accent/20 bg-aria-accent/10 p-2 text-aria-accent"><UserPlus size={17} /></div>
          <div><h2 className="text-sm font-semibold text-aria-text1">Add a member</h2><p className="mt-1 text-xs text-aria-text4">Create a separate account for each person. Passwords must be at least 12 characters.</p></div>
        </div>
        <form className="grid gap-3 md:grid-cols-[1.2fr_1fr_150px_auto] md:items-end" onSubmit={(event) => { event.preventDefault(); createUser.mutate(); }}>
          <div className="space-y-1.5"><Label htmlFor="member-email">Work email</Label><Input id="member-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></div>
          <div className="space-y-1.5"><Label htmlFor="member-password">Temporary password</Label><Input id="member-password" type="password" minLength={12} value={password} onChange={(event) => setPassword(event.target.value)} required /></div>
          <div className="space-y-1.5"><Label htmlFor="member-role">Role</Label><select id="member-role" value={role} onChange={(event) => setRole(event.target.value as OrganizationRole)} className="h-9 w-full rounded-md border border-[var(--aria-border)] bg-transparent px-2 text-sm text-aria-text2">{ROLES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></div>
          <Button type="submit" disabled={createUser.isPending}>{createUser.isPending ? "Adding..." : "Add member"}</Button>
        </form>
      </GlassCard>

      <GlassCard className="overflow-hidden">
        <div className="border-b border-[var(--aria-border-subtle)] px-5 py-4"><h2 className="text-sm font-semibold text-aria-text1">Members</h2></div>
        {users.isLoading && <p className="p-5 text-sm text-aria-text4">Loading members...</p>}
        {users.error && <p className="p-5 text-sm text-red-400">You need an administrator role to manage this organization.</p>}
        <div className="divide-y divide-[var(--aria-border-subtle)]">{users.data?.users.map((user) => <div key={user.id} className="px-5 py-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-center"><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium text-aria-text1">{user.email}</p><p className="mt-0.5 text-[11px] text-aria-text4">{user.disabled_at ? "Access disabled" : `Joined ${new Date(user.created_at).toLocaleDateString()}`}</p></div>
          <select aria-label={`Role for ${user.email}`} value={user.role} disabled={Boolean(user.disabled_at) || updateUser.isPending} onChange={(event) => updateUser.mutate({ userId: user.id, updates: { role: event.target.value as OrganizationRole } })} className="h-8 rounded-md border border-[var(--aria-border)] bg-transparent px-2 text-xs capitalize text-aria-text2">{ROLES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select>
          <Button size="sm" variant="outline" disabled={resetPassword.isPending} onClick={() => { setResettingUserId(resettingUserId === user.id ? null : user.id); setReplacementPassword(""); }}>Reset password</Button>
          <Button size="sm" variant="outline" disabled={updateUser.isPending} onClick={() => updateUser.mutate({ userId: user.id, updates: { disabled: !user.disabled_at } })}>{user.disabled_at ? <><ShieldCheck size={13} className="mr-1" />Restore</> : <><UserX size={13} className="mr-1" />Disable</>}</Button></div>
          {resettingUserId === user.id && <form className="mt-3 flex flex-col gap-2 rounded-lg border border-[var(--aria-border)] bg-[var(--aria-surface-2)]/30 p-3 md:flex-row md:items-end" onSubmit={(event) => { event.preventDefault(); resetPassword.mutate({ userId: user.id, password: replacementPassword }); }}><div className="flex-1 space-y-1"><Label htmlFor={`reset-${user.id}`}>New temporary password</Label><Input id={`reset-${user.id}`} type="password" minLength={12} value={replacementPassword} onChange={(event) => setReplacementPassword(event.target.value)} required /></div><Button type="submit" disabled={replacementPassword.length < 12 || resetPassword.isPending}>{resetPassword.isPending ? "Resetting..." : "Set password"}</Button></form>}
        </div>)}</div>
      </GlassCard>

      <GlassCard className="overflow-hidden"><div className="border-b border-[var(--aria-border-subtle)] px-5 py-4"><h2 className="text-sm font-semibold text-aria-text1">Recent activity</h2></div><div className="divide-y divide-[var(--aria-border-subtle)]">{audit.data?.events.slice(0, 25).map((event) => <div key={event.id} className="flex items-center justify-between gap-4 px-5 py-3"><span className="text-xs capitalize text-aria-text2">{eventLabel(event.event_type)}</span><time className="shrink-0 text-[11px] text-aria-text4">{new Date(event.created_at).toLocaleString()}</time></div>) || <p className="p-5 text-sm text-aria-text4">Loading activity...</p>}</div></GlassCard>
    </div>
  </div>;
}
