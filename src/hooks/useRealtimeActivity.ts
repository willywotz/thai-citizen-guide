import { useState, useEffect, useCallback, useRef } from 'react';
import { supabase } from '@/integrations/supabase/client';

export interface RealtimeEvent {
  id: string;
  title: string;
  agencies: string[];
  status: string;
  timestamp: Date;
}

const MAX_EVENTS = 50;
const BUCKET_SECONDS = 10;
const MAX_BUCKETS = 30; // 5 minutes of data

export interface ActivityBucket {
  time: string;
  count: number;
}

export function useRealtimeActivity() {
  const [events, setEvents] = useState<RealtimeEvent[]>([]);
  const [buckets, setBuckets] = useState<ActivityBucket[]>(() => initBuckets());
  const bucketsRef = useRef(buckets);
  bucketsRef.current = buckets;

  // Initialize with empty buckets
  function initBuckets(): ActivityBucket[] {
    const now = Date.now();
    return Array.from({ length: MAX_BUCKETS }, (_, i) => ({
      time: formatTime(new Date(now - (MAX_BUCKETS - 1 - i) * BUCKET_SECONDS * 1000)),
      count: 0,
    }));
  }

  function formatTime(d: Date) {
    return d.toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }

  // Shift buckets every BUCKET_SECONDS
  useEffect(() => {
    const interval = setInterval(() => {
      setBuckets((prev) => {
        const newBucket: ActivityBucket = {
          time: formatTime(new Date()),
          count: 0,
        };
        return [...prev.slice(1), newBucket];
      });
    }, BUCKET_SECONDS * 1000);
    return () => clearInterval(interval);
  }, []);

  const handleInsert = useCallback((payload: any) => {
    const row = payload.new;
    const event: RealtimeEvent = {
      id: row.id,
      title: row.title || 'สนทนาใหม่',
      agencies: row.agencies || [],
      status: row.status || 'success',
      timestamp: new Date(),
    };

    setEvents((prev) => [event, ...prev].slice(0, MAX_EVENTS));

    // Increment the last bucket
    setBuckets((prev) => {
      const updated = [...prev];
      updated[updated.length - 1] = {
        ...updated[updated.length - 1],
        count: updated[updated.length - 1].count + 1,
      };
      return updated;
    });
  }, []);

  useEffect(() => {
    const channel = supabase
      .channel('realtime-conversations')
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'conversations' },
        handleInsert
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [handleInsert]);

  return { events, buckets, totalLive: events.length };
}
