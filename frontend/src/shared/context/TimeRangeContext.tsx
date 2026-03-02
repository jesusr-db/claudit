import { createContext, useContext, useState, type ReactNode } from "react";

interface TimeRangeContextValue {
  days: number;
  setDays: (days: number) => void;
}

const TimeRangeContext = createContext<TimeRangeContextValue>({
  days: 7,
  setDays: () => {},
});

export function TimeRangeProvider({ children }: { children: ReactNode }) {
  const [days, setDays] = useState(7);
  return (
    <TimeRangeContext.Provider value={{ days, setDays }}>
      {children}
    </TimeRangeContext.Provider>
  );
}

export function useTimeRange() {
  return useContext(TimeRangeContext);
}
