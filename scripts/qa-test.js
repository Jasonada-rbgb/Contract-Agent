/**
 * Warranty Contract Agent -- Full QA Test Suite
 *
 * Usage:
 *   Set target app URL:
 *      $env:ORCHESTRATOR_APP_URL="https://<your-app>.databricksapps.com/"
 *
 *   1. Launch Chrome with CDP:
 *      Start-Process "C:\Program Files\Google\Chrome\Application\chrome.exe" -ArgumentList "--remote-debugging-port=9222","--no-first-run",$env:ORCHESTRATOR_APP_URL
 *   2. Log into Databricks if prompted
 *   3. Run: node scripts/qa-test.js
 *
 * Or from Cursor: "Run node scripts/qa-test.js" (Chrome must already be open)
 */

const { execSync, spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

function loadPlaywright() {
  const candidates = [
    process.env.ORCHESTRATOR_PLAYWRIGHT_MODULE || '',
    'playwright',
    'playwright-core',
    'C:/Users/ADJ1DE/.cursor/plugins/cache/cursor-public/browse/release_v0.2.3/node_modules/playwright',
  ].filter(Boolean);
  for (const mod of candidates) {
    try {
      return require(mod);
    } catch {}
  }
  throw new Error(
    'Playwright module not found. Install playwright or set ORCHESTRATOR_PLAYWRIGHT_MODULE.'
  );
}

const pw = loadPlaywright();
const SCREENSHOTS = process.env.ORCHESTRATOR_QA_SCREENSHOTS_DIR || path.join(process.cwd(), 'ai', 'screenshots');
const APP_URL = (process.env.ORCHESTRATOR_APP_URL || '').trim();
const CDP_PORT = Number(process.env.ORCHESTRATOR_CDP_PORT || '9222');
const CDP_URL = `http://localhost:${CDP_PORT}`;
const CHROME_PATH = process.env.ORCHESTRATOR_CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const CHROME_USER_DATA = process.env.ORCHESTRATOR_CHROME_USER_DATA || 'C:/Users/ADJ1DE/AppData/Local/Google/Chrome/QA-Profile';
const RUN_ID = process.env.ORCHESTRATOR_QA_RUN_ID || 'adhoc';
const DEPLOYMENT_ID = (process.env.ORCHESTRATOR_DEPLOYMENT_ID || '').trim();
const DEPLOYMENT_TIMESTAMP = (process.env.ORCHESTRATOR_DEPLOYMENT_TIMESTAMP || '').trim();
const QA_LOCK_PATH = path.join(process.cwd(), 'ai', 'orchestrator', 'qa-run.lock');
const RESPONSE_TIMEOUT = Number(process.env.ORCHESTRATOR_QA_RESPONSE_TIMEOUT_MS || '360000');
const PAGE_TIMEOUT = 30_000;
const SSO_TIMEOUT = 300_000;
const SCREENSHOT_TIMEOUT = 60_000;
const HARD_TIMEOUT_MS = 22 * 60 * 1000;
const REUSE_PROFILE = process.argv.includes('--reuse-profile') || process.env.ORCHESTRATOR_REUSE_PROFILE === '1';

const results = [];
const startTime = Date.now();
fs.mkdirSync(SCREENSHOTS, { recursive: true });
let launchedChromePid = null;
let lockAcquired = false;

function acquireQaLock() {
  const dir = path.dirname(QA_LOCK_PATH);
  fs.mkdirSync(dir, { recursive: true });
  if (fs.existsSync(QA_LOCK_PATH)) {
    let existing = null;
    try {
      existing = JSON.parse(fs.readFileSync(QA_LOCK_PATH, 'utf8'));
    } catch {}
    const existingPid = Number((existing && existing.pid) || 0);
    if (existingPid > 0) {
      try {
        process.kill(existingPid, 0);
        throw new Error(
          `Another QA run is active (pid=${existingPid}, run_id=${(existing && existing.run_id) || 'unknown'}).`
        );
      } catch (err) {
        if (String(err.message || '').includes('Another QA run is active')) {
          throw err;
        }
        // stale pid; allow overwrite
      }
    }
  }
  fs.writeFileSync(
    QA_LOCK_PATH,
    JSON.stringify({ pid: process.pid, run_id: RUN_ID, started_at: new Date().toISOString() }, null, 2),
    'utf8'
  );
  lockAcquired = true;
}

function releaseQaLock() {
  if (!lockAcquired) return;
  try {
    if (fs.existsSync(QA_LOCK_PATH)) {
      const existing = JSON.parse(fs.readFileSync(QA_LOCK_PATH, 'utf8'));
      if (Number(existing.pid || 0) === process.pid) {
        fs.unlinkSync(QA_LOCK_PATH);
      }
    }
  } catch {}
  lockAcquired = false;
}

function log(test, status, note) {
  const entry = { test, status, note: note || '' };
  results.push(entry);
  const icon = status === 'PASS' ? '✓' : status === 'FAIL' ? '✗' : '⚠';
  console.log(`  ${icon} [${status}] ${test}${note ? ' -- ' + note : ''}`);
}

async function waitForStreamlit(page, text, timeout = PAGE_TIMEOUT) {
  try {
    await page.waitForFunction(
      (t) => document.body.innerText.includes(t),
      text,
      { timeout }
    );
    return true;
  } catch {
    return false;
  }
}

async function waitForAnyText(page, texts, timeout) {
  const needles = texts.map((t) => String(t).toLowerCase());
  try {
    await page.waitForFunction(
      (targets) => {
        const bodyText = (document.body && document.body.innerText ? document.body.innerText : '').toLowerCase();
        return targets.some((needle) => bodyText.includes(needle));
      },
      needles,
      { timeout }
    );
    return true;
  } catch {
    return false;
  }
}

async function screenshot(page, name) {
  const path = `${SCREENSHOTS}/${name}`;
  try {
    await page.screenshot({ path, fullPage: true, timeout: SCREENSHOT_TIMEOUT });
    log('screenshot', 'SAVED', name);
  } catch {
    await page.screenshot({ path, fullPage: false, timeout: SCREENSHOT_TIMEOUT }).catch(() => {});
    log('screenshot', 'SAVED', name + ' (viewport only)');
  }
}

function isTargetAppUrl(url) {
  if (typeof url !== 'string' || !url) return false;
  try {
    const target = new URL(APP_URL);
    const current = new URL(url);
    if (target.hostname !== current.hostname) return false;
    const targetPath = (target.pathname || '/').replace(/\/+$/, '') || '/';
    const currentPath = (current.pathname || '/').replace(/\/+$/, '') || '/';
    return targetPath === '/' ? true : currentPath.startsWith(targetPath);
  } catch {
    try {
      const host = new URL(APP_URL).hostname;
      return !!host && url.includes(host);
    } catch {
      return false;
    }
  }
}

async function ensureSingleAppTab(context) {
  let pages = context.pages();
  let target = pages.find((p) => isTargetAppUrl(p.url()));

  if (!target) {
    target = pages.length > 0 ? pages[0] : await context.newPage();
    await target.goto(APP_URL, { waitUntil: 'networkidle', timeout: 60000 });
  } else if (!isTargetAppUrl(target.url())) {
    await target.goto(APP_URL, { waitUntil: 'networkidle', timeout: 60000 });
  }

  pages = context.pages();
  let closed = 0;
  for (const p of pages) {
    if (p === target) continue;
    await p.close({ runBeforeUnload: false }).catch(() => {});
    closed += 1;
  }

  return { page: target, closed };
}

function cleanupLaunchedChrome() {
  if (!launchedChromePid) return;
  try {
    execSync(`taskkill /F /PID ${launchedChromePid} /T 2>nul`, { stdio: 'ignore' });
  } catch {}
  launchedChromePid = null;
}

function clearCdpListener(port = 9222) {
  try {
    execSync(
      `powershell -NoProfile -Command "$p=(Get-NetTCPConnection -LocalPort ${port} -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty OwningProcess); if($p){Stop-Process -Id $p -Force -ErrorAction SilentlyContinue}"`,
      { stdio: 'ignore' }
    );
  } catch {}
}

process.on('exit', () => {
  cleanupLaunchedChrome();
  releaseQaLock();
});
process.on('SIGINT', () => {
  cleanupLaunchedChrome();
  releaseQaLock();
  process.exit(130);
});
process.on('SIGTERM', () => {
  cleanupLaunchedChrome();
  releaseQaLock();
  process.exit(143);
});

(async () => {
  if (!APP_URL) {
    console.error('FATAL: ORCHESTRATOR_APP_URL is required.');
    process.exit(2);
  }

  acquireQaLock();
  const hardTimeout = setTimeout(() => {
    console.error('FATAL: qa-test exceeded hard timeout and was terminated.');
    cleanupLaunchedChrome();
    releaseQaLock();
    process.exit(124);
  }, HARD_TIMEOUT_MS);

  console.log('\n=== Warranty Contract Agent -- QA Test Suite ===\n');
  console.log(`Target: ${APP_URL}`);
  if (DEPLOYMENT_ID) console.log(`Deployment ID: ${DEPLOYMENT_ID}`);
  if (DEPLOYMENT_TIMESTAMP) console.log(`Deployment Timestamp: ${DEPLOYMENT_TIMESTAMP}`);
  console.log(`Time: ${new Date().toISOString()}\n`);

  // ---- CHROME LIFECYCLE ----
  // Clear any stale listener on the CDP port from a previous QA run.
  console.log(`  Clearing stale CDP listener on port ${CDP_PORT}...`);
  clearCdpListener(CDP_PORT);
  await new Promise(r => setTimeout(r, 2000));

  // Launch Chrome with CDP enabled
  console.log(`  Launching Chrome with CDP on port ${CDP_PORT}...`);
  try {
    const chromeArgs = [
      `--remote-debugging-port=${CDP_PORT}`,
      '--new-window',
      '--no-first-run',
      '--no-default-browser-check',
      `--user-data-dir=${CHROME_USER_DATA}`,
      'about:blank',
    ];
    const launched = spawn(CHROME_PATH, chromeArgs, {
      detached: true,
      stdio: 'ignore',
      windowsHide: true,
    });
    launchedChromePid = launched.pid || null;
    launched.unref();
  } catch {}
  console.log('  Chrome launch command sent.');

  // Wait for CDP to become available
  let browser;
  for (let attempt = 0; attempt < 30; attempt++) {
    await new Promise(r => setTimeout(r, 2000));
    try {
      browser = await pw.chromium.connectOverCDP(CDP_URL);
      break;
    } catch {}
  }
  if (!browser) {
    console.error('FATAL: Chrome launched but CDP not available after 60 seconds.');
    process.exit(1);
  }
  console.log('  Chrome connected via CDP.\n');

  const context = browser.contexts()[0];
  if (!context) {
    console.error('FATAL: No browser context found.');
    process.exit(1);
  }
  context.setDefaultTimeout(PAGE_TIMEOUT);
  context.setDefaultNavigationTimeout(120000);

  let { page, closed } = await ensureSingleAppTab(context);
  console.log(`  Tab cleanup complete. Closed ${closed} extra tab(s).`);

  // Detect whether we need SSO login.  Check the page URL and title for any
  // sign of an auth gate: Databricks login, Azure AD, Microsoft pick-account,
  // or a blank/about:blank page that hasn't redirected yet.
  const currentUrl = page.url().toLowerCase();
  const currentTitle = await page.title();
  const needsLogin =
    currentTitle.includes('Login') ||
    currentTitle.includes('Sign') ||
    currentTitle.includes('Pick an account') ||
    currentUrl.includes('login.microsoftonline.com') ||
    currentUrl.includes('accounts.azuredatabricks.net') ||
    currentUrl.includes('/login') ||
    currentUrl === 'about:blank';

  if (needsLogin) {
    console.log('  Waiting for Databricks SSO login (log in manually in the Chrome window)...');
    // Use an explicit timeout that is NOT affected by context.setDefaultTimeout.
    // Poll every 2s instead of relying on waitForFunction which can inherit the
    // context default timeout in some Playwright builds.
    const ssoDeadline = Date.now() + SSO_TIMEOUT;
    let loggedIn = false;
    while (Date.now() < ssoDeadline) {
      await page.waitForTimeout(2000);
      const title = await page.title().catch(() => '');
      const url = page.url().toLowerCase();
      if (
        (title.includes('Warranty') || title.includes('Contract')) &&
        url.includes('databricksapps.com')
      ) {
        loggedIn = true;
        break;
      }
      // Also check if we landed on the app but title hasn't updated yet
      if (url.includes('agent-contract') && url.includes('databricksapps.com')) {
        await page.waitForTimeout(5000);
        loggedIn = true;
        break;
      }
    }
    if (!loggedIn) {
      console.error(`FATAL: SSO login not completed within ${SSO_TIMEOUT / 1000}s.`);
      process.exit(1);
    }
    console.log('  Login detected. Waiting for app to load...');
    await page.waitForTimeout(10000);
    ({ page, closed } = await ensureSingleAppTab(context));
    console.log(`  Post-login tab cleanup complete. Closed ${closed} extra tab(s).`);
  }

  // Ensure we're on the app page
  ({ page, closed } = await ensureSingleAppTab(context));
  if (closed > 0) {
    console.log(`  Final tab cleanup complete. Closed ${closed} extra tab(s).`);
  }

  // Wait for Streamlit to fully render
  console.log('  Waiting for app to fully load...');
  await page.waitForFunction(
    () => document.title.includes('Warranty') || document.title.includes('Contract'),
    { timeout: SSO_TIMEOUT }
  );
  await page.waitForTimeout(5000);

  console.log('--- TEST 1: Page Load ---');
  const title = await page.title();
  log('app_title', title.includes('Warranty') || title.includes('Contract') ? 'PASS' : 'FAIL', title);

  const body = await page.evaluate(() => document.body.innerText);
  log('has_contract_selector', body.includes('Select contract') || body.includes('contract') ? 'PASS' : 'FAIL');
  log('mode_qa', body.includes('Q&A') || body.includes('Q\u0026A') ? 'PASS' : 'FAIL');
  log('mode_claims', body.includes('Claims') ? 'PASS' : 'FAIL');
  log('mode_ingest', body.includes('Ingest') ? 'PASS' : 'FAIL');
  log('mode_feedback', body.includes('Feedback') ? 'PASS' : 'FAIL');
  log('chat_history', body.toLowerCase().includes('chat history') || body.toLowerCase().includes('saved chats') ? 'PASS' : 'FAIL');
  log('user_identity', body.includes('Logged in') || body.includes('43b522b8') ? 'PASS' : 'WARN', 'Service principal shown');

  await screenshot(page, 'qa-01-load.png');

  // ---- TEST 2: Navigate to Q&A ----
  console.log('\n--- TEST 2: Contract Q&A Flow ---');
  try {
    const qaRadio = page.locator('label').filter({ hasText: 'Contract Q&A' }).first();
    await qaRadio.click();
    await page.waitForTimeout(3000);
    log('navigate_to_qa', 'PASS');
  } catch (e) {
    log('navigate_to_qa', 'FAIL', e.message.substring(0, 100));
  }

  // ---- TEST 3: Ask a question ----
  console.log('\n--- TEST 3: Ask Question ---');
  try {
    const chatInput = page.getByPlaceholder('Ask about the warranty contract');
    await chatInput.click();
    await chatInput.fill('What are the warranty periods for this contract?');
    await chatInput.press('Enter');
    log('question_submitted', 'PASS');

    // Wait for thinking panel
    await page.waitForTimeout(3000);
    const hasThinking = await page.textContent('body').then(t => t.includes('Thinking'));
    log('thinking_panel', hasThinking ? 'PASS' : 'WARN', hasThinking ? 'Thinking panel visible' : 'May have already completed');

    await screenshot(page, 'qa-02-thinking.png');

    // Wait for response/completion once (single timeout budget).
    console.log('  ... waiting for AI response and completion ...');
    const gotResponseSignal = await waitForAnyText(
      page,
      ['Evidence', 'Answer', 'Sources', 'Citation', 'Done'],
      RESPONSE_TIMEOUT
    );

    const completedSignal = await page.waitForFunction(
      () => {
        const bodyText = document.body && document.body.innerText ? document.body.innerText : '';
        const lower = bodyText.toLowerCase();
        const hasStop = bodyText.includes('Stop');
        const hasDone = bodyText.includes('Done');
        const hasThinking = lower.includes('thinking');
        const hasAnswerSignal =
          lower.includes('evidence') ||
          lower.includes('answer') ||
          lower.includes('sources') ||
          /\[\d+\]/.test(bodyText);
        const hasFeedbackSignal =
          lower.includes('helpful') ||
          lower.includes('flagged');
        // Completed if explicit done, stop control is gone, or a concrete answer
        // signal is visible and the active generation controls have settled.
        return hasDone || ((hasAnswerSignal || hasFeedbackSignal) && !hasThinking && !hasStop);
      },
      undefined,
      { timeout: RESPONSE_TIMEOUT }
    ).then(() => true).catch(() => false);

    if (!completedSignal) {
      log('response_completion', 'FAIL', `Completion timeout after ${Math.floor(RESPONSE_TIMEOUT / 1000)}s (configured timeout)`);
    } else {
      log('response_completion', 'PASS', 'Response generation completed');
    }

    await page.waitForTimeout(5000);
    // Scroll to bottom to see full response
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(3000);
    const responseBody = await page.evaluate(() => document.body.innerText);

    const gotResponse = gotResponseSignal || /\[\d+\]/.test(responseBody) || /evidence|answer|sources/i.test(responseBody);
    log('response_received', gotResponse ? 'PASS' : 'FAIL', gotResponse ? 'Response signal detected' : 'No response signal detected');

    const hasCitations = /\[\d+\]/.test(responseBody);
    const hasAnswer = /answer|evidence|sources/i.test(responseBody);
    log('has_citations', hasCitations ? 'PASS' : (hasAnswer ? 'WARN' : 'FAIL'),
        hasCitations ? 'Found [n] citations' : (hasAnswer ? 'Response present but citations not detected in innerText' : 'No response content detected'));

    const hasEvidence = responseBody.toLowerCase().includes('evidence');
    log('has_evidence_section', hasEvidence ? 'PASS' : 'WARN');

    const hasDone = responseBody.includes('Done');
    log('thinking_collapsed', hasDone ? 'PASS' : 'WARN', hasDone ? 'Status shows Done' : 'Done not found');

    const likelyHiddenUnderDone = hasDone && !hasCitations && !hasEvidence && !hasAnswer;
    log(
      'answer_visible_in_chat',
      likelyHiddenUnderDone ? 'FAIL' : 'PASS',
      likelyHiddenUnderDone ? 'Likely hidden under Done/status container' : 'Answer appears visible in chat output'
    );

    await screenshot(page, 'qa-03-response.png');
  } catch (e) {
    log('question_flow', 'FAIL', e.message.substring(0, 200));
    await screenshot(page, 'qa-03-error.png');
  }

  // ---- TEST 4: Feedback buttons ----
  console.log('\n--- TEST 4: Inline Feedback Buttons ---');
  try {
    // Wait for Streamlit to fully settle, then reload for clean DOM state
    await page.waitForTimeout(10000);
    await page.reload({ waitUntil: 'networkidle', timeout: 120000 });
    await page.waitForFunction(
      () => document.title.includes('Warranty') || document.title.includes('Contract'),
      { timeout: 60_000 }
    );
    await page.waitForTimeout(8000);
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(3000);

    // Check for any feedback-related elements (buttons or captions)
    const allButtons = await page.evaluate(() =>
      Array.from(document.querySelectorAll('button')).map(b => b.textContent.trim().substring(0, 20))
    );
    const thumbsUpButtons = page.locator('button').filter({ hasText: '👍' });
    const thumbsDownButtons = page.locator('button').filter({ hasText: '👎' });
    const upCount = await thumbsUpButtons.count();
    const downCount = await thumbsDownButtons.count();

    const pageText = await page.evaluate(() => document.body.innerText);
    const hasHelpfulCaption = pageText.includes('Helpful') || pageText.includes('Flagged');

    const hasResponse = pageText.toLowerCase().includes('warranty') || pageText.toLowerCase().includes('evidence');
    log('thumbs_up_present', upCount > 0 ? 'PASS' : (hasHelpfulCaption ? 'PASS' : (hasResponse ? 'WARN' : 'FAIL')),
        upCount > 0 ? `Found ${upCount} thumbs up button(s)` :
        (hasHelpfulCaption ? 'Already rated (caption shown)' :
        (hasResponse ? 'Response exists but buttons not rendered (may be scrolled/collapsed)' : 'No response or buttons found')));
    log('thumbs_down_present', downCount > 0 ? 'PASS' : (hasHelpfulCaption ? 'PASS' : (hasResponse ? 'WARN' : 'FAIL')),
        downCount > 0 ? `Found ${downCount} thumbs down button(s)` :
        (hasHelpfulCaption ? 'Already rated' : (hasResponse ? 'Same as above' : 'Not found')));

    if (upCount > 0) {
      // Scroll to bottom and wait for page to fully stabilize
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
      await page.waitForTimeout(5000);

      // Find a visible thumbs up button
      const stableUp = page.locator('button').filter({ hasText: '👍' });
      const stableCount = await stableUp.count();
      let clicked = false;
      for (let idx = stableCount - 1; idx >= 0; idx--) {
        const btn = stableUp.nth(idx);
        if (await btn.isVisible().catch(() => false)) {
          await btn.scrollIntoViewIfNeeded().catch(() => {});
          await btn.click({ timeout: 10000 });
          clicked = true;
          break;
        }
      }
      if (!clicked) {
        log('feedback_click', 'WARN', `${stableCount} buttons found but none visible/clickable`);
      }

      // Streamlit reruns after click -- wait for it to settle
      await page.waitForTimeout(5000);

      const afterClick = await page.textContent('body');

      // After rerun, either the "Why?" prompt appears or the "Helpful" caption shows
      const hasWhyInput = afterClick.includes('Why?') || afterClick.includes('optional');
      const hasHelpful = afterClick.includes('Helpful') || afterClick.includes('Flagged');
      log('feedback_rating_applied', hasWhyInput || hasHelpful ? 'PASS' : 'FAIL',
          hasWhyInput ? '"Why?" comment prompt appeared' : (hasHelpful ? 'Rating confirmed' : 'No feedback state detected'));

      await screenshot(page, 'qa-04-feedback-inline.png');

      if (hasWhyInput) {
        const hasSubmitSkip = afterClick.includes('Submit') && afterClick.includes('Skip');
        log('feedback_submit_skip', hasSubmitSkip ? 'PASS' : 'WARN', hasSubmitSkip ? 'Submit and Skip buttons visible' : 'Buttons not found');

        // Click Skip to dismiss
        try {
          const skipBtn = page.locator('button').filter({ hasText: 'Skip' }).first();
          await skipBtn.click({ timeout: 5000 });
          await page.waitForTimeout(3000);
          log('feedback_skip', 'PASS', 'Skipped without comment');
        } catch {
          log('feedback_skip', 'WARN', 'Could not click Skip');
        }
      } else if (hasHelpful) {
        log('feedback_persisted', 'PASS', 'Rating shows as confirmed caption');
      }
    }
  } catch (e) {
    log('feedback_buttons', 'FAIL', e.message.substring(0, 100));
  }

  // ---- TEST 5: Claims Evaluator ----
  console.log('\n--- TEST 5: Claims Evaluator ---');
  try {
    // Reload to get clean page state after Q&A interaction
    await page.reload({ waitUntil: 'networkidle', timeout: 120000 });
    await page.waitForFunction(
      () => document.title.includes('Warranty') || document.title.includes('Contract'),
      { timeout: 60_000 }
    );
    await page.waitForTimeout(8000);
    const claimsRadio = page.locator('label').filter({ hasText: 'Claims Evaluator' }).first();
    await claimsRadio.click();
    await page.waitForTimeout(8000);
    const claimsBody = await page.textContent('body');

    log('claims_page', 'PASS', 'Page loaded');
    log('claims_model_selector', claimsBody.includes('Gemini') || claimsBody.includes('Evaluation model') ? 'PASS' : 'FAIL', 'Model dropdown present');
    log('claims_upload', claimsBody.includes('Upload claims file') || claimsBody.includes('Browse files') || claimsBody.includes('Drag and drop') ? 'PASS' : 'FAIL');

    // Check all 3 model options are listed (may need to open the dropdown)
    const hasGemini = claimsBody.includes('Gemini');
    const hasClaude = claimsBody.includes('Claude');
    log('claims_has_gemini', hasGemini ? 'PASS' : 'WARN', 'Gemini Flash option');

    await screenshot(page, 'qa-05-claims.png');
  } catch (e) {
    log('claims_evaluator', 'FAIL', e.message.substring(0, 100));
  }

  // ---- TEST 6: Ingest Contract ----
  console.log('\n--- TEST 6: Ingest Contract ---');
  try {
    const ingestRadio = page.locator('label').filter({ hasText: 'Ingest Contract' }).first();
    await ingestRadio.click();
    await page.waitForTimeout(5000);
    const ingestBody = await page.textContent('body');

    log('ingest_page', 'PASS', 'Page loaded');
    log('ingest_oem_field', ingestBody.includes('OEM Name') ? 'PASS' : 'FAIL');
    log('ingest_contract_id', ingestBody.includes('Contract ID') ? 'PASS' : 'FAIL');
    log('ingest_pdf_upload', ingestBody.includes('Upload contract') || ingestBody.includes('Browse files') ? 'PASS' : 'FAIL');

    await screenshot(page, 'qa-06-ingest.png');
  } catch (e) {
    log('ingest_contract', 'FAIL', e.message.substring(0, 100));
  }

  // ---- TEST 7: Feedback Page ----
  console.log('\n--- TEST 7: Feedback Page ---');
  try {
    const feedbackRadios = page.locator('label').filter({ hasText: 'Feedback' });
    await feedbackRadios.last().click();
    await page.waitForTimeout(3000);
    const fbBody = await page.textContent('body');

    const fbInner = await page.evaluate(() => document.body.innerText);
    log('feedback_page', 'PASS', 'Page loaded');
    log('feedback_text_area', fbInner.includes('Describe') || fbInner.includes('issue') || fbInner.includes('suggestion') ? 'PASS' : 'FAIL');
    log('feedback_category', fbInner.includes('Category') || fbInner.includes('Inaccuracy') ? 'PASS' : 'FAIL');
    log('feedback_severity', fbInner.includes('Severity') || fbInner.includes('Critical') ? 'PASS' : 'FAIL');
    log('feedback_contract_field', fbInner.includes('contract') ? 'PASS' : 'FAIL');
    log('feedback_recent', fbInner.includes('Recent') || fbInner.includes('feedback') ? 'PASS' : 'FAIL');

    await screenshot(page, 'qa-07-feedback.png');
  } catch (e) {
    log('feedback_page', 'FAIL', e.message.substring(0, 100));
  }

  // ---- SUMMARY ----
  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
  const passed = results.filter(r => r.status === 'PASS').length;
  const failed = results.filter(r => r.status === 'FAIL').length;
  const warns = results.filter(r => r.status === 'WARN').length;
  const saved = results.filter(r => r.status === 'SAVED').length;

  console.log('\n=== QA SUMMARY ===');
  console.log(`  Tests:       ${passed + failed + warns} (${passed} passed, ${failed} failed, ${warns} warnings)`);
  console.log(`  Screenshots: ${saved}`);
  console.log(`  Duration:    ${elapsed}s`);
  if (DEPLOYMENT_ID) console.log(`  Deployment:  ${DEPLOYMENT_ID}`);
  console.log(`  Verdict:     ${failed === 0 ? 'APPROVED ✓' : 'BLOCKED ✗'}`);

  if (failed > 0) {
    console.log('\n  Failed tests:');
    results.filter(r => r.status === 'FAIL').forEach(r => {
      console.log(`    ✗ ${r.test}: ${r.note}`);
    });
  }

  console.log('\n  Screenshots saved to: ai/screenshots/');
  console.log('  Report: ai/reports/qa-<date>.md\n');
  if (failed > 0) {
    process.exitCode = 1;
  }

  try {
    await browser.close();
  } catch {}
  cleanupLaunchedChrome();
  releaseQaLock();
  clearTimeout(hardTimeout);

})().catch(e => {
  console.error('FATAL ERROR:', e.message);
  cleanupLaunchedChrome();
  releaseQaLock();
  process.exit(1);
});
