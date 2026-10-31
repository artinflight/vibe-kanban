// Read-only acceptance against the branch frontend and existing green gateway.
// Preference writes and their subscription snapshots stay inside each test browser.
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const base = process.env.VK_TEST_BASE;
const backend = process.env.VK_TEST_BACKEND;
const output = process.env.VK_TEST_OUTPUT;
if (
  !base ||
  !backend ||
  !output ||
  !process.env.PLAYWRIGHT_MODULE ||
  !process.env.PLAYWRIGHT_WS_BUNDLE
) {
  throw new Error(
    'Set VK_TEST_BASE, VK_TEST_BACKEND, VK_TEST_OUTPUT on mounted SSD, and PLAYWRIGHT_MODULE'
  );
}
await mkdir(resolve(output, 'browser-tmp'), { recursive: true });
process.env.TMPDIR = resolve(output, 'browser-tmp');
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE);
const { default: bundle } = await import(process.env.PLAYWRIGHT_WS_BUNDLE);
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH,
  headless: true,
});
const results = [];
await mkdir(output, { recursive: true });
try {
  for (const width of [360, 412, 767, 768, 1440]) {
    const mobile = width < 768;
    const context = await browser.newContext({
      viewport: { width, height: mobile ? 915 : 1000 },
      isMobile: mobile,
      hasTouch: mobile,
    });
    context.setDefaultTimeout(15000);
    const sockets = new Set();
    let savedPreferences = { type: 'UI_PREFERENCES', data: {} };
    if (width === 1440) {
      const projects = (
        await (await context.request.get(`${backend}/api/projects`)).json()
      ).data;
      // Saved sidebar customizations must also drive chip abbreviations/colors.
      savedPreferences.data.local_project_customizations = Object.fromEntries(
        projects.map((project, index) => [
          project.id,
          {
            abbreviation: `X${index.toString(36).toUpperCase()}`,
            color: '202 82% 82%',
          },
        ])
      );
    }
    let closing = false;
    let interceptedWrites = 0;
    const errors = [];
    await context.route(/\/(?:api|v1)\//, async (route) => {
      const request = route.request();
      const path = new URL(request.url()).pathname;
      if (
        ['GET', 'HEAD'].includes(request.method()) ||
        (request.method() === 'POST' && path === '/api/workspaces/summaries')
      ) {
        return route.continue({
          headers: { ...request.headers(), origin: new URL(backend).origin },
        });
      }
      interceptedWrites++;
      const payload = request.postDataJSON();
      if (payload?.payload?.type === 'UI_PREFERENCES')
        savedPreferences = payload.payload;
      return route.fulfill({ json: { success: true, data: payload ?? null } });
    });
    await context.routeWebSocket('**/api/**', (route) => {
      const source = new URL(route.url());
      if (
        source.pathname.includes('/scratch/') &&
        source.pathname.includes('UI_PREFERENCES')
      ) {
        route.send(
          JSON.stringify({
            JsonPatch: [
              {
                op: 'replace',
                path: '/scratch',
                value: savedPreferences ? { payload: savedPreferences } : null,
              },
            ],
          })
        );
        route.send(JSON.stringify({ Ready: true }));
        return;
      }
      const url = new URL(source.pathname + source.search, backend);
      url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
      const socket = new bundle.ws(url, { origin: new URL(backend).origin });
      sockets.add(socket);
      socket.on('message', (data) => {
        if (!closing) route.send(data.toString());
      });
      socket.on('error', () => {
        if (!closing) route.close();
      });
      socket.on('close', () => {
        sockets.delete(socket);
        if (!closing) route.close();
      });
      route.onClose(() => socket.close());
    });
    const page = await context.newPage();
    page.on('pageerror', (error) => {
      errors.push(error.message);
      console.log(error.message);
    });
    page.on('response', (response) => {
      if (response.status() >= 500)
        console.log(
          'HTTP',
          response.status(),
          new URL(response.url()).pathname
        );
    });
    const assertFits = async () =>
      assert(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth + 1
        ),
        'Page must fit viewport'
      );
    const touchTarget = async (locator) => {
      await locator.evaluate(async (element) => {
        const panel = element.closest('[role="menu"]') ?? element;
        await Promise.all(
          panel
            .getAnimations({ subtree: true })
            .map((animation) => animation.finished.catch(() => {}))
        );
      });
      const box = await locator.boundingBox();
      assert(
        box && box.height >= 48 && box.width >= 48,
        `Touch target: ${JSON.stringify(box)}`
      );
    };
    try {
      console.log(`Testing workspace filters at ${width}px`);
      await page.goto(base + '/workspaces', {
        waitUntil: 'domcontentloaded',
        timeout: 180000,
      });
      await page
        .getByRole('textbox', { name: 'Search workspaces' })
        .waitFor({ timeout: 180000 });
      if (!mobile) {
        assert.equal(await page.locator('.phone-project-filter').count(), 0);
        const chips = page.getByRole('group', { name: 'Project', exact: true });
        await chips.waitFor();
        const all = chips.getByRole('button', {
          name: 'All projects',
          exact: true,
        });
        const noProject = chips.getByRole('button', {
          name: 'No project',
          exact: true,
        });
        assert.equal(await all.getAttribute('aria-pressed'), 'true');
        await page.getByRole('button', { name: 'All', exact: true }).click();
        await page.waitForFunction(
          () =>
            document.querySelectorAll('.workspace-project-filter-chip').length >
            2
        );
        const projectName = await chips
          .getByRole('button')
          .nth(2)
          .getAttribute('title');
        // Options populate independently; keep the chosen project stable when
        // an earlier alphabetic option arrives between actions.
        const project = chips.getByRole('button', {
          name: projectName,
          exact: true,
        });
        await page.waitForFunction((name) => {
          const chip = [
            ...document.querySelectorAll('.workspace-project-filter-chip'),
          ].find((button) => button.getAttribute('aria-label') === name);
          const sidebar = [
            ...document.querySelectorAll('button[aria-label]'),
          ].find(
            (button) =>
              !button.classList.contains('workspace-project-filter-chip') &&
              [name, `${name} (needs review)`].includes(
                button.getAttribute('aria-label')
              )
          );
          if (!chip || !sidebar) return false;
          return (
            chip.textContent.trim() === sidebar.textContent.trim() &&
            getComputedStyle(chip).backgroundColor ===
              getComputedStyle(sidebar).backgroundColor &&
            getComputedStyle(chip).color === getComputedStyle(sidebar).color
          );
        }, projectName);
        const chipBox = await project.boundingBox();
        assert(
          chipBox.height <= 28 && chipBox.width <= 60,
          'Abbreviated project bubbles must stay compact'
        );
        assert((await project.innerText()).trim().length <= 3);
        if (width === 1440)
          assert.match((await project.innerText()).trim(), /^X[0-9A-Z]+$/);
        await project.click();
        assert.equal(await project.getAttribute('aria-pressed'), 'true');
        assert.equal(await all.getAttribute('aria-pressed'), 'false');
        const projects = (
          await (await context.request.get(`${backend}/api/projects`)).json()
        ).data;
        const selectedProject = projects.find(
          (item) => item.name === projectName
        );
        assert(selectedProject);
        const linkedResponse = await (
          await context.request.get(
            `${backend}/v1/fallback/project_workspaces?project_id=${selectedProject.id}`
          )
        ).json();
        const linkedIds = new Set(
          (linkedResponse.workspaces ?? linkedResponse.data.workspaces).map(
            (item) => item.local_workspace_id
          )
        );
        const workspaces = (
          await (await context.request.get(`${backend}/api/workspaces`)).json()
        ).data;
        const expectedNames = workspaces
          .filter((item) => !item.archived && linkedIds.has(item.id))
          .map((item) => item.name);
        await page.waitForFunction((names) => {
          const rows = [
            ...document.querySelectorAll(
              '.mobile-workspace-card > button > div:first-child'
            ),
          ];
          return (
            (names.length === 0 || rows.length > 0) &&
            rows.every((row) => names.includes(row.textContent.trim()))
          );
        }, expectedNames);
        await noProject.click();
        assert.equal(await noProject.getAttribute('aria-pressed'), 'true');
        assert.equal(await project.getAttribute('aria-pressed'), 'true');
        const deadline = Date.now() + 15000;
        while (
          savedPreferences.data?.workspace_filters?.project_ids?.length !== 2 &&
          Date.now() < deadline
        )
          await page.waitForTimeout(100);
        assert.equal(
          savedPreferences.data.workspace_filters.project_ids.length,
          2
        );
        await page.reload({ waitUntil: 'domcontentloaded' });
        await chips.waitFor();
        await page.waitForFunction(
          () =>
            [
              ...document.querySelectorAll(
                '.workspace-project-filter-chip[aria-pressed="true"]'
              ),
            ].length === 2
        );
        await page
          .getByRole('button', { name: 'Filter workspaces', exact: true })
          .click();
        const dialog = page.getByRole('dialog', { name: 'Filter workspaces' });
        await dialog
          .getByRole('button', { name: /Project/ })
          .getByText('2', { exact: true })
          .waitFor();
        await dialog
          .getByRole('button', { name: 'Close', exact: true })
          .click();
        // Resizing preserves state while swapping between desktop chips and the
        // approved phone dropdown.
        await page.setViewportSize({ width: 412, height: 915 });
        const mobileSelector = page.locator('.phone-project-filter');
        await mobileSelector.waitFor();
        assert.match(await mobileSelector.innerText(), /2/);
        await page.setViewportSize({ width, height: 1000 });
        await chips.waitFor();
        assert.equal(await project.getAttribute('aria-pressed'), 'true');
        await project.focus();
        await page.keyboard.press('Space');
        assert.equal(await project.getAttribute('aria-pressed'), 'false');
        assert.equal(await noProject.getAttribute('aria-pressed'), 'true');
        await noProject.click();
        assert.equal(await all.getAttribute('aria-pressed'), 'true');
        await project.click();
        await all.click();
        assert.equal(await project.getAttribute('aria-pressed'), 'false');
        assert.equal(await all.getAttribute('aria-pressed'), 'true');
        // Constrain the landing list to the actual desktop sidebar width and
        // verify that chips scroll in one row without widening their parent.
        await chips.evaluate((element) => {
          element.parentElement.parentElement.parentElement.style.width =
            '300px';
        });
        const layout = await chips.evaluate((element) => ({
          width: element.clientWidth,
          scrollWidth: element.scrollWidth,
          tops: [...element.querySelectorAll('button')].map(
            (button) => button.offsetTop
          ),
        }));
        assert(layout.width <= 300);
        assert(layout.scrollWidth > layout.width);
        assert.equal(new Set(layout.tops).size, 1);
        const last = chips.getByRole('button').last();
        await last.focus();
        assert(await chips.evaluate((element) => element.scrollLeft > 0));
        await assertFits();
        await page.screenshot({
          path: resolve(output, `desktop-project-chips-${width}.png`),
        });
        console.log(
          `${width}px desktop chips: filtering, multi-select, persistence, resize, keyboard and sidebar fit passed`
        );
      } else {
        const selector = page.locator('.phone-project-filter');
        const toolbar = page.locator('.phone-workspace-filters');
        await selector.waitFor();
        console.log(`${width}px workspace list ready`);
        assert.equal(
          await page.getByRole('button', { name: 'List options' }).count(),
          0
        );
        await touchTarget(selector);
        await touchTarget(
          toolbar.getByRole('button', {
            name: 'Filter workspaces',
            exact: true,
          })
        );
        await touchTarget(
          toolbar.getByRole('button', { name: 'Sort workspaces', exact: true })
        );
        await page.getByRole('button', { name: 'All', exact: true }).click();
        await selector.click();
        const menu = page.locator('.phone-project-filter-menu');
        const all = menu.getByRole('menuitemcheckbox', {
          name: 'All projects',
          exact: true,
        });
        await all.waitFor();
        assert.equal(await all.getAttribute('aria-checked'), 'true');
        const noProject = menu.getByRole('menuitemcheckbox', {
          name: 'No project',
          exact: true,
        });
        await touchTarget(noProject);
        // Project data arrives independently of the workspace list.
        await page.waitForFunction(
          () =>
            document.querySelectorAll(
              '.phone-project-filter-menu [role="menuitemcheckbox"]'
            ).length > 2
        );
        const project = menu.getByRole('menuitemcheckbox').nth(2);
        const projectName = (await project.innerText()).trim();
        await project.tap();
        assert.equal(await project.getAttribute('aria-checked'), 'true');
        assert.equal(await selector.innerText(), projectName);
        // Verify the selected project actually narrows the workspace rows.
        const projects = (
          await (await context.request.get(`${backend}/api/projects`)).json()
        ).data;
        const selectedProject = projects.find(
          (item) => item.name === projectName
        );
        assert(
          selectedProject,
          'Selected project must exist in the same backend'
        );
        const linkedResponse = await (
          await context.request.get(
            `${backend}/v1/fallback/project_workspaces?project_id=${selectedProject.id}`
          )
        ).json();
        const linked =
          linkedResponse.workspaces ?? linkedResponse.data.workspaces;
        const linkedIds = new Set(
          linked.map((item) => item.local_workspace_id)
        );
        const workspaces = (
          await (await context.request.get(`${backend}/api/workspaces`)).json()
        ).data;
        const expectedNames = workspaces
          .filter((item) => !item.archived && linkedIds.has(item.id))
          .map((item) => item.name);
        await page.waitForFunction((names) => {
          const rows = [...document.querySelectorAll('.phone-workspace-name')];
          return (
            (names.length === 0 || rows.length > 0) &&
            rows.every((row) => names.includes(row.textContent.trim()))
          );
        }, expectedNames);
        console.log(`${width}px project selection narrows workspace rows`);
        await noProject.tap();
        assert.equal(await noProject.getAttribute('aria-checked'), 'true');
        assert.match(await selector.innerText(), /2/);
        await page.keyboard.press('Escape');
        await page.waitForFunction(
          () => !document.querySelector('.phone-project-filter-menu')
        );
        assert.equal(
          await selector.evaluate(
            (element) => element === document.activeElement
          ),
          true
        );
        await page.waitForFunction(() =>
          document
            .querySelector('.phone-project-filter')
            .textContent.includes('2')
        );
        // Read back the actual UI preference save, then hydrate it after reload.
        const deadline = Date.now() + 15000;
        while (
          savedPreferences?.data?.workspace_filters?.project_ids?.length !==
            2 &&
          Date.now() < deadline
        ) {
          await page.waitForTimeout(100);
        }
        assert.equal(
          savedPreferences?.data.workspace_filters.project_ids.length,
          2
        );
        console.log(`${width}px preferences saved locally; checking reload`);
        await page.reload({ waitUntil: 'domcontentloaded' });
        await selector.waitFor();
        await page.waitForFunction(() =>
          document
            .querySelector('.phone-project-filter')
            .textContent.includes('2')
        );
        // The existing dialog and direct selector must share the same state.
        await toolbar
          .getByRole('button', { name: 'Filter workspaces', exact: true })
          .click();
        const dialog = page.getByRole('dialog', { name: 'Filter workspaces' });
        await dialog.waitFor();
        // Verify shared selection through the existing dialog's project badge.
        // Keep this acceptance focused on the new direct selector rather than
        // the existing nested dropdown's Escape dismissal behavior.
        await dialog
          .getByRole('button', { name: /Project/ })
          .getByText('2', { exact: true })
          .waitFor();
        await dialog
          .getByRole('button', { name: 'Close', exact: true })
          .click();
        await selector.click();
        await all.click();
        assert.equal(await all.getAttribute('aria-checked'), 'true');
        assert.equal(await selector.innerText(), 'All projects');
        await page.keyboard.press('Escape');
        // Search and archive remain usable with the toolbar visible.
        await page
          .getByRole('textbox', { name: 'Search workspaces' })
          .fill('no-such-mobile-filter-workspace');
        await page
          .getByRole('heading', { name: 'No matching workspaces' })
          .waitFor();
        await selector.waitFor();
        await page.getByRole('textbox', { name: 'Search workspaces' }).fill('');
        await page
          .getByRole('button', { name: 'Archived workspaces', exact: true })
          .click();
        await page
          .getByRole('heading', { name: 'Archive', exact: true })
          .waitFor();
        await selector.click();
        await noProject.click();
        assert.equal(await selector.innerText(), 'No project');
        await page.keyboard.press('Escape');
        await assertFits();
        await page.screenshot({
          path: resolve(output, `workspace-filters-${width}.png`),
        });
      }
      assert.deepEqual(errors, []);
      results.push({ width, passed: true, interceptedWrites });
    } catch (error) {
      console.error('Browser acceptance failure:', error.message, errors);
      await page
        .screenshot({
          path: resolve(output, `failure-${width}.png`),
          timeout: 5000,
        })
        .catch(() => {});
      throw error;
    } finally {
      closing = true;
      for (const socket of sockets) socket.close();
      await context.close();
    }
  }
  await writeFile(
    resolve(output, 'results.json'),
    JSON.stringify(results, null, 2)
  );
  console.log(JSON.stringify(results));
} finally {
  await browser.close();
}
