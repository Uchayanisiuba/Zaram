interface ICommandRegistry {
  register(manifest: CommandManifest): void;
  unregister(id: string): void;
  search(query: string, context?: ContextPacket[]): CommandManifest[];
  execute(id: string, payload?: any): Promise<Result<void, CommandError>>;
}