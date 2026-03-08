import { useState, useEffect, useCallback, useRef } from 'react';
import { BASE_URL } from '@/lib/apiClient';

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

function formatTime(d: Date) {
  return d.toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function initBuckets(): ActivityBucket[] {
  const now = Date.now();
  return Array.from({ length: MAX_BUCKETS }, (_, i) => ({
    time: formatTime(new Date(now - (MAX_BUCKETS - 1 - i) * BUCKET_SECONDS * 1000)),
    count: 0,
  }));
}

export function useRealtimeActivity() {
  const [events, setEvents] = useState<RealtimeEvent[]>([]);
  const [buckets, setBuckets] = useState<ActivityBucket[]>(() => initBuckets());
  const bucketsRef = useRef(buckets);
  bucketsRef.current = buckets;

  // Shift buckets every BUCKET_SECONDS
  useEffect(() => {
    const interval = setInterval(() => {
      setBuckets((prev) => {
        const newBucket: ActivityBucket = { time: formatTime(new Date()), count: 0 };
        return [...prev.slice(1), newBucket];
      });
    }, BUCKET_SECONDS * 1000);
    return () => clearInterval(interval);
  }, []);

  const handleEvent = useCallback((data: any) => {
    if (data.type === 'ping') return;
    const event: RealtimeEvent = {
      id: data.id || crypto.randomUUID(),
      title: data.title || 'สนทนาใหม่',
      agencies: data.agencies || [],
      status: data.status || 'success',
      timestamp: new Date(),
    };
    setEvents((prev) => [event, ...prev].slice(0, MAX_EVENTS));
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
    const wsUrl = BASE_URL.replace(/^http/, 'ws') + '/ws/activity';
    let ws: WebSocket;
    let reconnectTimer: ReturnType<typeof setTimeout>;

    function connect() {
      ws = new WebSocket(wsUrl);
      ws.onmessage = (e) => {
        try {
          handleEvent(JSON.parse(e.data));
        } catch { /* ignore */ }
      };
      ws.onclose = () => {
        reconnectTimer = setTimeout(connect, 5000);
      };
    }

    connect();
    return () => {
      clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, [handleEvent]);

  return { events, buckets, totalLive: events.length };
}
