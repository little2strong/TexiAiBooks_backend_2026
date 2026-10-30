import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach, vi } from 'vitest';
afterEach(cleanup);
Object.defineProperty(window, 'matchMedia', { writable: true, value: vi.fn().mockImplementation(query => ({ matches: false, media: query, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} })) });
globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
const getStyle = window.getComputedStyle;
window.getComputedStyle = element => getStyle(element);
