import { useQuery } from '@tanstack/react-query';
import { getAuditLog, type AuditLogParams } from './auditApi';

const KEY = 'audit-log';

export function useAuditLog(params: AuditLogParams) {
  return useQuery({
    queryKey: [KEY, params],
    queryFn: () => getAuditLog(params),
    staleTime: 30_000,
    placeholderData: (prev) => prev,
  });
}
