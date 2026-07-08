import { useContext } from 'react';
import { ZaramContext } from '../context/ZaramContext';

export const useZaram = () => {
  const context = useContext(ZaramContext);
  
  if (!context) {
    throw new Error('useZaram must be used within ZaramProvider');
  }
  
  return context;
};
