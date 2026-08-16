/**
 * Entry point for the ambient overlay window.
 *
 * One document serves two windows, told apart by the fragment: the panel is
 * `ambient.html`, the screen-edge handle is `ambient.html#handle`. They share
 * an entry because they are one feature and the handle is four elements —
 * a second HTML file and a second bundle for a strip of colour would be
 * ceremony.
 *
 * No `StrictMode` double-render here, unlike `main.tsx`. The panel is created
 * hidden at boot and lives for the life of the application, so the mount
 * effects that would run twice include the one that asks the backend where
 * answers come from.
 */
import ReactDOM from 'react-dom/client';
import AmbientPanel from './surfaces/AmbientPanel';
import EdgeHandle from './surfaces/EdgeHandle';
import { installApiCredential } from './services/apiCredential';
import './surfaces/ambient.css';

const isHandle = window.location.hash === '#handle';

// The overlay is a second entry point, so it installs the credential itself.
// This is exactly the "one more client forgets the header" problem the wrapper
// exists to prevent, appearing one level up — the wrapper is per document, and
// this is a second document.
void installApiCredential().then(() => {
  ReactDOM.createRoot(document.getElementById('root')!).render(
    isHandle ? <EdgeHandle /> : <AmbientPanel />,
  );
});
