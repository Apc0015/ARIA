import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useEnabledSources() {
  const client = useQueryClient();
  const settings = useQuery({ queryKey: ["source-settings"], queryFn: api.sourceSettings.get });
  const save = useMutation({
    mutationFn: api.sourceSettings.save,
    onSuccess: (data) => client.setQueryData(["source-settings"], data),
  });
  const overrides = settings.data?.enabled_sources ?? {};

  /** Whether a source is active. Falls back to `defaultVal` if user never touched it. */
  function isEnabled(id: string, defaultVal: boolean): boolean {
    return id in overrides ? overrides[id] : defaultVal;
  }

  /** Flip the toggle for a source. */
  function toggle(id: string, defaultVal: boolean) {
    const current = id in overrides ? overrides[id] : defaultVal;
    save.mutate({ ...overrides, [id]: !current });
  }

  return { isEnabled, toggle, isLoading: settings.isLoading, error: settings.error };
}
