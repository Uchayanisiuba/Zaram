// ✅ DO
import { describe, it, expect } from 'vitest';
import { createUser } from './user';

describe('createUser', () => {
  it('creates a user with valid data', () => {
    const user = createUser({
      name: 'John',
      email: 'john@example.com'
    });
    
    expect(user.id).toBeDefined();
    expect(user.name).toBe('John');
    expect(user.email).toBe('john@example.com');
  });
  
  it('throws on invalid email', () => {
    expect(() => 
      createUser({ name: 'John', email: 'invalid' })
    ).toThrow('Invalid email');
  });
});

// ❌ DON'T
// No tests