-- Trigger: notify MCP server on any agency row change
-- Sends pg_notify('agency_changes', json) on INSERT / UPDATE / DELETE

CREATE OR REPLACE FUNCTION public.notify_agency_change()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  payload jsonb;
  rec     record;
BEGIN
  -- Use NEW for insert/update, OLD for delete
  rec := COALESCE(NEW, OLD);

  payload := jsonb_build_object(
    'event',      TG_OP,          -- 'INSERT' | 'UPDATE' | 'DELETE'
    'id',         rec.id,
    'name',       rec.name,
    'short_name', rec.short_name,
    'status',     rec.status,
    'ts',         extract(epoch from now())
  );

  PERFORM pg_notify('agency_changes', payload::text);
  RETURN NEW;
END;
$$;

-- Drop and recreate so it's idempotent
DROP TRIGGER IF EXISTS trg_agency_notify ON public.agencies;

CREATE TRIGGER trg_agency_notify
AFTER INSERT OR UPDATE OR DELETE ON public.agencies
FOR EACH ROW EXECUTE FUNCTION public.notify_agency_change();
