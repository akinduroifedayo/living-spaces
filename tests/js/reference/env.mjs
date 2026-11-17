import { registerHooks } from 'node:module';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

registerHooks({
  resolve(specifier, context, next) {
    const vendors = {preact: 'preact.mjs', 'preact/hooks': 'hooks.mjs', plot: 'plot.mjs', markdown: 'markdown.mjs'};
    if (vendors[specifier]) return {url: pathToFileURL(resolve('src/living-spaces/runtime/vendor', vendors[specifier])).href, shortCircuit: true};
    return next(specifier, context);
  }
});
