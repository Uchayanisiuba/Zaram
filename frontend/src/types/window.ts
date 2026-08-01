export interface Window {
  id: string;
  position: { x: number; y: number };
  size: { width: number; height: number };
  isFocused: boolean;
}