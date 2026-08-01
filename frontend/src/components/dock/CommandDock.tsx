import { motion } from 'framer-motion';
import LivingOrb from '../orb/LivingOrb';
import { useSurfaceStore, WorkspaceType } from '@/stores/surfaceStore';

const Icon = ({ path, className = 'h-6 w-6' }: { path: string; className?: string }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    fill="none"
    viewBox="0 0 24 24"
    strokeWidth={1.5}
    stroke="currentColor"
    className={className}
  >
    <path strokeLinecap="round" strokeLinejoin="round" d={path} />
  </svg>
);

const WorkspaceButton = ({
  type,
  title,
  iconPath,
}: {
  type: WorkspaceType;
  title: string;
  iconPath: string;
}) => {
  const { openSurface, focusSurface, surfaces, focusedSurfaceId } = useSurfaceStore();
  const surface = surfaces.find((s) => s.type === type);
  const isFocused = surface && surface.id === focusedSurfaceId;

  const handleClick = () => {
    if (surface) {
      focusSurface(surface.id);
    } else {
      openSurface(type, title);
    }
  };

  return (
    <motion.button
      className={`relative flex h-12 w-12 items-center justify-center rounded-full ${
        isFocused ? 'text-white' : 'text-neutral-400 hover:text-white'
      }`}
      onClick={handleClick}
      whileHover={{ scale: 1.1 }}
      whileTap={{ scale: 0.9 }}
    >
      <Icon path={iconPath} />
      {isFocused && (
        <motion.div
          layoutId="activeWorkspaceIndicator"
          className="absolute -bottom-1 h-1 w-6 rounded-full bg-white"
        />
      )}
    </motion.button>
  );
};

const CommandDock = () => {
  return (
    <footer
      className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2"
      style={{
        zIndex: 50,
      }}
    >
      <div
        className="flex items-center gap-4 rounded-full p-2"
        style={{
          background: 'rgba(23, 23, 23, 0.6)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          boxShadow: '0 8px 32px 0 rgba(0, 0, 0, 0.37)',
          backdropFilter: 'blur(12px)',
        }}
      >
        <WorkspaceButton
          type="knowledge"
          title="Knowledge"
          iconPath="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25"
        />
        <WorkspaceButton
          type="build"
          title="Build"
          iconPath="M6.75 7.5l3 2.25-3 2.25m4.5 0h3m-9 8.25h13.5A2.25 2.25 0 0021 18V6a2.25 2.25 0 00-2.25-2.25H5.25A2.25 2.25 0 003 6v12a2.25 2.25 0 002.25 2.25z"
        />
        <WorkspaceButton
          type="memory"
          title="Memory"
          iconPath="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
        />
        <LivingOrb />
        <WorkspaceButton
          type="create"
          title="Create"
          iconPath="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10"
        />
        <div className="h-12 w-12" />
        <div className="h-12 w-12" />
      </div>
    </footer>
  );
};

export default CommandDock;