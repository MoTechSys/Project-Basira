/* Basira logo components — inline SVG (no network request, no CLS). */
import * as React from 'react';

export interface LogoMarkProps extends React.SVGProps<SVGSVGElement> {
  size?: number | string;
  /** 'tile' = gradient rounded tile (default); 'ondark' = no tile for dark surfaces; 'mono' = currentColor */
  variant?: 'tile' | 'ondark' | 'mono';
  title?: string;
}

export function LogoMark({ size = 40, variant = 'tile', title = 'بصيرة — Basira', ...rest }: LogoMarkProps) {
  const id = React.useId();
  const gid = `bsg-${id}`;
  const eye = variant === 'mono' ? 'currentColor' : '#F2F4FF';
  const star = variant === 'mono' ? 'currentColor' : '#2EF2C2';
  const check = variant === 'mono' ? '#fff' : '#12183F';
  return (
    // Basira correction (BRAND_AUDIT §2.9): an empty `title` makes the mark decorative — no <title>, no
    // role="img", aria-hidden — so a parent link's visible wordmark stays its only accessible name.
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 64 64"
      width={size}
      height={size}
      {...(title ? { role: 'img', 'aria-label': title } : { 'aria-hidden': true, focusable: false })}
      {...rest}
    >
      {title ? <title>{title}</title> : null}
      {variant === 'tile' && (
        <>
          <defs>
            <linearGradient id={gid} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stopColor="#6150EA" />
              <stop offset="1" stopColor="#12183F" />
            </linearGradient>
          </defs>
          <rect width="64" height="64" rx="16" fill={`url(#${gid})`} />
        </>
      )}
      <path d="M9 32C15 20 23 15 32 15s17 5 23 17c-6 12-14 17-23 17S15 44 9 32z" fill="none" stroke={eye} strokeWidth={3.4} strokeLinejoin="round" />
      <path d="M32 20.5l3.43 3.21 4.7.16.16 4.7L43.5 32l-3.21 3.43-.16 4.7-4.7.16L32 43.5l-3.43-3.21-4.7-.16-.16-4.7L20.5 32l3.21-3.43.16-4.7 4.7-.16z" fill={star} />
      <path d="M27.2 32.2l3.3 3.3 6.4-7" fill="none" stroke={check} strokeWidth={2.8} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** Horizontal lockup — use the optimized SVG file via <img> for best caching; this wrapper picks light/dark. */
export function LogoHorizontal({ dark = false, height = 44, alt = 'بصيرة — Basira', base = '/brand/logo' }:
  { dark?: boolean; height?: number; alt?: string; base?: string }) {
  return (
    <img
      src={`${base}/logo-horizontal-${dark ? 'dark' : 'light'}.svg`}
      alt={alt}
      height={height}
      width={Math.round(height * (360 / 88))}
      decoding="async"
      fetchPriority="high"
    />
  );
}

export default LogoMark;
