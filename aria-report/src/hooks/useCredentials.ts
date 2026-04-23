import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useCredentials() {
  return useQuery({
    queryKey: ["credentials"],
    queryFn: api.credentials.get,
    staleTime: 30_000,
  });
}

export function useSaveCredentials() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.credentials.save,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["credentials"] }),
  });
}
