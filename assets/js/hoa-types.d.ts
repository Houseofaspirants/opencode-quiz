/* Shared ambient types for the type-checked plain JS the site ships.
 *
 * The project has no bundler and no transpile step (Vercel runs
 * `node scripts/build-index.mjs` and the pages load these .js files directly),
 * so type safety comes from `// @ts-check` + JSDoc rather than from a .ts
 * build: the types below describe globals the scripts attach to `window`, and
 * jsconfig.json turns the rest of the checking on in editors and in
 * scripts/ci.sh. Nothing here emits code. */

interface Window {
  /** The public API every page talks to; assigned at the bottom of core.js. */
  HOA: any;
  /** Google Analytics 4 loader (see core.js initAnalytics). */
  gtag: (...args: any[]) => void;
  /** GA4 queue; exists before the gtag.js snippet finishes loading. */
  dataLayer: any[];
  /** Seeded landing pages inject one object; absent on the classic quiz URL. */
  __HOA_QUIZ_SEED: any;
}
