// ✅ DO
import { render, screen, fireEvent } from '@testing-library/react';
import { Orb } from './Orb';

describe('Orb', () => {
  it('opens command palette on click', () => {
    const onInteract = vi.fn();
    render(<Orb state="idle" onInteract={onInteract} />);
    
    fireEvent.click(screen.getByRole('button', { name: /orb/i }));
    
    expect(onInteract).toHaveBeenCalledWith('openPalette');
  });
  
  it('is accessible', () => {
    render(<Orb state="idle" onInteract={() => {}} />);
    
    expect(screen.getByRole('button')).toHaveAttribute(
      'aria-label',
      'Zaram Orb, currently idle'
    );
  });
});