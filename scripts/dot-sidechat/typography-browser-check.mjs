import assert from 'node:assert/strict';

// Run against the compiled app with isolated API fixtures. The native workspace
// renderer supplies the reference; no assumed pixel value or backend write.
export async function checkDotTypography(page, reference) {
  const actual = await page.evaluate(() => {
    const style = (node) => {
      if (!node) return null;
      const css = getComputedStyle(node);
      return {
        size: css.fontSize,
        family: css.fontFamily,
        lineHeight: css.lineHeight,
      };
    };
    const panel = [...document.querySelectorAll('.dot-panel')].find(
      (node) => node.getClientRects().length
    );
    return {
      workspaceMessage: style(
        document.querySelector('.wysiwyg [contenteditable="false"] p')
      ),
      workspaceComposer: style(
        document.querySelector('.wysiwyg [contenteditable="true"]')
      ),
      messages: [...panel.querySelectorAll('.dot-message > p')].map(style),
      composer: style(panel.querySelector('.dot-composer textarea')),
      horizontalOverflow: document.documentElement.scrollWidth > innerWidth,
    };
  });
  const message = actual.workspaceMessage ?? reference?.message;
  const composer = actual.workspaceComposer ?? reference?.composer;
  assert.ok(message && composer, 'Measure native workspace reference first');
  assert.ok(actual.messages.length, 'Render at least one actual Dot message');
  for (const body of actual.messages) {
    assert.equal(body.size, message.size);
    assert.equal(body.family, message.family);
  }
  assert.equal(actual.composer.size, composer.size);
  assert.equal(actual.composer.family, composer.family);
  assert.equal(actual.horizontalOverflow, false);
  return actual;
}
