interface SurfaceBodyProps {
  children: React.ReactNode;
}

const SurfaceBody = ({ children }: SurfaceBodyProps) => {
  return (
    <div
      className="flex-1 overflow-y-auto p-6"
      style={{
        scrollbarWidth: 'thin',
        scrollbarColor: 'var(--glass-border) transparent',
      }}
    >
      {children}
    </div>
  );
};

export default SurfaceBody;