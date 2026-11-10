// @vitest-environment jsdom
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it } from 'vitest';
import { RequireRole } from './context';
import { session } from './session';
import type { Role } from '../api/types';

function signIn(role: Role) {
  session.start({ access_token: 'synthetic', expires_in: 60, staff: { id: 'staff', name: 'Synthetic', email: 'staff@example.invalid', role } });
}

function show(path: string) {
  return render(<MemoryRouter initialEntries={[path]}><Routes>
    <Route path="/" element={<RequireRole role="accountant"><p>Accountant dashboard</p></RequireRole>} />
    <Route path="/admin" element={<RequireRole role="admin"><p>Admin overview</p></RequireRole>} />
    <Route path="/admin/users" element={<RequireRole role="admin"><p>Staff accounts</p></RequireRole>} />
  </Routes></MemoryRouter>);
}

afterEach(() => session.end());

describe('each role stays in its own area', () => {
  it('sends an accountant who opens an admin page back to their dashboard', () => {
    signIn('accountant');
    show('/admin/users');
    expect(screen.getByText('Accountant dashboard')).toBeTruthy();
    expect(screen.queryByText('Staff accounts')).toBeNull();
  });
  it('sends an admin who opens the accountant dashboard to the admin overview', () => {
    signIn('admin');
    show('/');
    expect(screen.getByText('Admin overview')).toBeTruthy();
  });
  it('lets each role open its own pages', () => {
    signIn('admin');
    show('/admin/users');
    expect(screen.getByText('Staff accounts')).toBeTruthy();
  });
});
