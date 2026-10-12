/**
 * Specialized output renderer for cua-driver computer use tools.
 *
 * Handles:
 * - Screenshots (base64 PNG from get_desktop_state, get_window_state)
 * - Accessibility trees (structured JSON from get_window_state, get_accessibility_tree)
 * - Window lists (from list_windows)
 * - App lists (from list_apps)
 * - Verification results (from verify_state)
 * - Visual regions (from parse_visual_regions)
 */
import { useState } from 'react';
import { ChevronRight, ImageIcon, Code, Eye } from 'lucide-react';

interface CuaDriverOutputProps {
  tool: string;
  output: string;
  server: string;
}

/** Try to parse JSON output, return null if not valid JSON. */
function parseJson(text: string): any {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

/** Check if output is a base64 image. */
function isBase64Image(text: string): boolean {
  return text.startsWith('data:image/') || /^[A-Za-z0-9+/=]{100,}$/.test(text);
}

/** Render a screenshot from base64 or data URL. */
function Screenshot({ dataUrl }: { dataUrl: string }) {
  return (
    <div style={{ marginTop: 8 }}>
      <div className="flex items-center gap-2 mb-1">
        <ImageIcon size={12} style={{ color: 'var(--color-text-muted)' }} />
        <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
          Screenshot (click to expand)
        </span>
      </div>
      <img
        src={dataUrl}
        alt="Screenshot"
        style={{
          maxWidth: '100%',
          maxHeight: 400,
          borderRadius: 4,
          border: '1px solid var(--color-border-subtle)',
          cursor: 'zoom-in',
        }}
        onClick={(e) => {
          const img = e.currentTarget;
          window.open(img.src, '_blank');
        }}
      />
    </div>
  );
}

/** Render an accessibility tree with collapsible nodes. */
function AccessibilityTree({ tree }: { tree: any }) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const toggleNode = (path: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  const renderNode = (node: any, path: string = 'root', depth: number = 0) => {
    if (!node) return null;
    const isExpanded = expanded.has(path);
    const hasChildren = node.children && node.children.length > 0;

    return (
      <div key={path} style={{ marginLeft: depth * 16 }}>
        <div
          className="flex items-center gap-1 cursor-pointer select-none"
          onClick={() => hasChildren && toggleNode(path)}
          style={{ color: 'var(--color-text)' }}
        >
          {hasChildren && (
            <ChevronRight
              size={10}
              style={{
                transform: isExpanded ? 'rotate(90deg)' : 'none',
                color: 'var(--color-text-muted)',
                transition: 'transform 0.1s',
              }}
            />
          )}
          {!hasChildren && <span style={{ width: 10 }} />}
          <span className="font-mono text-[10px]" style={{ color: 'var(--color-text-faint)' }}>
            {node.element_token ? `${node.element_token} ` : ''}
          </span>
          <span className="font-mono text-[10px]">{node.role}</span>
          {node.label && (
            <span className="text-[10px]" style={{ color: 'var(--color-cyan-light)' }}>
              "{node.label}"
            </span>
          )}
          {node.frame && (
            <span className="text-[10px]" style={{ color: 'var(--color-text-faint)' }}>
              @{Math.round(node.frame.x)},{Math.round(node.frame.y)}
              {Math.round(node.frame.w)}×{Math.round(node.frame.h)}
            </span>
          )}
        </div>
        {isExpanded && hasChildren && (
          <div>{node.children!.map((child: any, i: number) => renderNode(child, `${path}.${i}`, depth + 1))}</div>
        )}
      </div>
    );
  };

  return (
    <div style={{ marginTop: 8 }}>
      <div className="flex items-center gap-2 mb-1">
        <Code size={12} style={{ color: 'var(--color-text-muted)' }} />
        <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
          Accessibility Tree ({tree.length ?? 'unknown'} nodes)
        </span>
        <button
          type="button"
          className="text-xs ml-auto px-2 py-0.5 rounded"
          style={{ color: 'var(--color-cyan-light)', border: '1px solid var(--color-border-subtle)' }}
          onClick={() => {
            setExpanded(new Set());
            tree.forEach((_: any, i: number) => setExpanded((prev) => new Set(prev).add(`root.${i}`)));
          }}
        >
          Expand All
        </button>
      </div>
      <div style={{ maxHeight: 400, overflow: 'auto', fontSize: '10px' }}>
        {Array.isArray(tree) ? tree.map((node: any, i: number) => renderNode(node, `root.${i}`)) : renderNode(tree, 'root')}
      </div>
    </div>
  );
}

/** Render a window list. */
function WindowList({ windows }: { windows: any[] }) {
  return (
    <div style={{ marginTop: 8 }}>
      <div className="flex items-center gap-2 mb-1">
        <ImageIcon size={12} style={{ color: 'var(--color-text-muted)' }} />
        <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
          {windows.length} window{windows.length !== 1 ? 's' : ''}
        </span>
      </div>
      <div style={{ maxHeight: 300, overflow: 'auto' }}>
        {windows.map((w: any, i: number) => (
          <div
            key={i}
            className="flex items-center gap-2 p-1.5 rounded hover:bg-white/5 cursor-pointer"
            style={{ border: '1px solid var(--color-border-subtle)', marginBottom: 4 }}
          >
            <div style={{ minWidth: 60, fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--color-text-faint)' }}>
              PID: {w.pid}
            </div>
            <div style={{ flex: 1, minWidth: 0, fontSize: '11px', color: 'var(--color-text)' }}>
              {w.title || w.app || 'Untitled'}
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--color-text-faint)' }}>
              {w.bounds ? `${Math.round(w.bounds.x)},${Math.round(w.bounds.y)} ${Math.round(w.bounds.w)}×${Math.round(w.bounds.h)}` : ''}
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--color-text-faint)' }}>
              {w.window_id}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Render an app list. */
function AppList({ apps }: { apps: any[] }) {
  return (
    <div style={{ marginTop: 8 }}>
      <div className="flex items-center gap-2 mb-1">
        <ImageIcon size={12} style={{ color: 'var(--color-text-muted)' }} />
        <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
          {apps.length} app{apps.length !== 1 ? 's' : ''}
        </span>
      </div>
      <div style={{ maxHeight: 300, overflow: 'auto' }}>
        {apps.map((a: any, i: number) => (
          <div
            key={i}
            className="flex items-center gap-2 p-1.5 rounded hover:bg-white/5"
            style={{ border: '1px solid var(--color-border-subtle)', marginBottom: 4 }}
          >
            <div style={{ minWidth: 80, fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--color-text-faint)' }}>
              {a.running ? '●' : '○'} {a.pid ? `PID:${a.pid}` : ''}
            </div>
            <div style={{ flex: 1, minWidth: 0, fontSize: '11px', color: 'var(--color-text)' }}>
              {a.name || a.bundle_id || 'Unknown'}
            </div>
            <div style={{ fontSize: '10px', color: 'var(--color-text-faint)' }}>
              {a.running ? 'Running' : 'Installed'}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Render verification result. */
function VerificationResult({ result }: { result: any }) {
  const status = result?.predicates ? (result.predicates.every((p: any) => p.ok) ? 'passed' : 'failed') : 'unknown';
  return (
    <div style={{ marginTop: 8 }}>
      <div className="flex items-center gap-2 mb-1">
        <span className="text-xs" style={{ color: status === 'passed' ? 'var(--color-emerald)' : 'var(--color-amber)' }}>
          {status.toUpperCase()}
        </span>
      </div>
      <pre style={{ fontSize: '10px', maxHeight: 200, overflow: 'auto' }}>
        {JSON.stringify(result, null, 2)}
      </pre>
    </div>
  );
}

/** Main component that routes to the right renderer. */
export default function CuaDriverOutput({ output }: CuaDriverOutputProps) {
  const parsed = parseJson(output);

  // Check for screenshot in various locations
  const screenshot = parsed?.screenshot || parsed?.image;
  const hasScreenshot = screenshot && isBase64Image(screenshot);

  // Accessibility tree
  const tree = parsed?.tree || parsed?.elements || parsed?.accessibility_tree;

  // Window list
  const windows = parsed?.windows || (Array.isArray(parsed) ? parsed : null);

  // App list
  const apps = parsed?.apps;

  // Verification result
  const verification = parsed?.predicates !== undefined ? parsed : null;

  // Visual regions
  const regions = parsed?.regions;

  // If we have a screenshot, show it prominently
  if (hasScreenshot) {
    return (
      <div>
        <Screenshot dataUrl={screenshot.startsWith('data:') ? screenshot : `data:image/png;base64,${screenshot}`} />
        {tree && <AccessibilityTree tree={tree} />}
        {windows && <WindowList windows={windows} />}
        {apps && <AppList apps={apps} />}
        {verification && <VerificationResult result={verification} />}
        {regions && <VisualRegions regions={regions} />}
        {!tree && !windows && !apps && !verification && !regions && (
          <pre style={{ marginTop: 8, fontSize: '10px', maxHeight: 200, overflow: 'auto' }}>
            {output.slice(0, 5000)}
          </pre>
        )}
      </div>
    );
  }

  // If we have an accessibility tree without screenshot
  if (tree) {
    return <AccessibilityTree tree={tree} />;
  }

  // Window list
  if (windows) {
    return <WindowList windows={windows} />;
  }

  // App list
  if (apps) {
    return <AppList apps={apps} />;
  }

  // Verification
  if (verification) {
    return <VerificationResult result={verification} />;
  }

  // Visual regions
  if (regions) {
    return <VisualRegions regions={regions} />;
  }

  // Fallback to plain text
  return null;
}

/** Render visual regions from parse_visual_regions. */
function VisualRegions({ regions }: { regions: any }) {
  if (!regions?.text_regions && !regions?.icon_regions) return null;

  return (
    <div style={{ marginTop: 8 }}>
      <div className="flex items-center gap-2 mb-1">
        <Eye size={12} style={{ color: 'var(--color-text-muted)' }} />
        <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
          Visual Regions
        </span>
      </div>
      <pre style={{ fontSize: '10px', maxHeight: 300, overflow: 'auto' }}>
        {JSON.stringify(regions, null, 2)}
      </pre>
    </div>
  );
}