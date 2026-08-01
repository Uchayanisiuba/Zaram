interface IContextGraph {
  addPacket(packet: ContextPacket): void;
  getActiveContext(): ContextPacket[];
  clearEphemeral(): void;
  onContextUpdate(listener: (context: ContextPacket[]) => void): UnsubscribeFn;
}