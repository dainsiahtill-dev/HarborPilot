import { useState } from 'react';
import type { TestEvent } from '../types';

const MAX_EVENTS = 500;

export const useTestEvents = () => {
  const [events, setEvents] = useState<TestEvent[]>([]);

  const addEvent = (event: TestEvent) => {
    setEvents((prev) => {
      const next = [...prev, event];
      if (next.length <= MAX_EVENTS) return next;
      return next.slice(next.length - MAX_EVENTS);
    });
  };

  const resetEvents = () => setEvents([]);

  return { events, addEvent, resetEvents };
};
