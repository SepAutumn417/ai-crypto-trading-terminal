import { create } from 'zustand';

interface SystemState {
  executionEnabled: boolean;
  killSwitch: boolean;
  setExecutionEnabled: (v: boolean) => void;
  setKillSwitch: (v: boolean) => void;
}

export const useSystemStore = create<SystemState>((set) => ({
  executionEnabled: false,
  killSwitch: true,
  setExecutionEnabled: (v) => set({ executionEnabled: v }),
  setKillSwitch: (v) => set({ killSwitch: v }),
}));