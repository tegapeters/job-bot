"""
Auto-submitter — LinkedIn Easy Apply via Playwright.
Review-first: shows each job, asks Y/N, then submits via Easy Apply.
"""
import asyncio
import json
import re
import time
from pathlib import Path
from playwright.async_api import async_playwright, Page, TimeoutError as PWTimeout

from config import RESUME_PATH, APPLICANT_INFO, AUTO_APPLY_MIN_SCORE

COOKIES_FILE = Path(__file__).parent / "linkedin_cookies.json"


# ── Session management ───────────────────────────────────────────────────────

async def _save_linkedin_session():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        ctx = await browser.new_context()
        page = await ctx.new_page()
        await page.goto("https://www.linkedin.com/login")
        print("\n  Browser opened — log in to LinkedIn, then press Enter here...")
        input("  Press Enter once you're logged in → ")
        cookies = await ctx.cookies()
        COOKIES_FILE.write_text(json.dumps(cookies))
        print(f"  ✅ Session saved.")
        await browser.close()


def linkedin_login():
    asyncio.run(_save_linkedin_session())


async def _get_browser_context(p):
    browser = await p.chromium.launch(headless=False)
    ctx = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )
    )
    if COOKIES_FILE.exists():
        cookies = json.loads(COOKIES_FILE.read_text())
        await ctx.add_cookies(cookies)
    else:
        print("  ⚠️  No LinkedIn session found. Run: python main.py linkedin-login")
    return browser, ctx


# ── Easy Apply ───────────────────────────────────────────────────────────────

async def _handle_easy_apply_modal(page: Page, job: dict) -> bool:
    """
    Walk through the Easy Apply multi-step modal.
    Handles: contact info, resume upload, screening questions, review, submit.
    """
    info = APPLICANT_INFO
    max_steps = 10

    for step in range(max_steps):
        await asyncio.sleep(1.5)

        # Check if we've reached the confirmation screen
        if await page.locator("h3:has-text('Application submitted')").count():
            return True
        if await page.locator("div:has-text('Your application was sent')").count():
            return True

        # ── Phone number ──
        phone_input = page.locator("input[id*='phoneNumber'], input[aria-label*='Phone']")
        if await phone_input.count():
            await phone_input.first.fill(info["phone"])

        # ── Resume upload ──
        file_input = page.locator("input[type='file']")
        if await file_input.count():
            try:
                await file_input.set_input_files(RESUME_PATH)
                await asyncio.sleep(1.5)
            except Exception:
                pass

        # ── Text / textarea questions ──
        # Fill numeric experience fields with "5"
        number_inputs = page.locator("input[type='text'][id*='numeric'], input[type='number']")
        for i in range(await number_inputs.count()):
            inp = number_inputs.nth(i)
            val = await inp.input_value()
            if not val:
                await inp.fill("5")

        # Yes/No radio buttons — default to first option (usually Yes)
        radios = page.locator("fieldset input[type='radio']")
        radio_count = await radios.count()
        for i in range(0, radio_count, 2):  # step 2: pick first of each pair
            try:
                radio = radios.nth(i)
                if not await radio.is_checked():
                    await radio.check()
            except Exception:
                pass

        # Select dropdowns — pick first non-empty option
        selects = page.locator("select")
        for i in range(await selects.count()):
            sel = selects.nth(i)
            val = await sel.input_value()
            if not val:
                options = await sel.locator("option").all()
                for opt in options[1:]:  # skip placeholder
                    opt_val = await opt.get_attribute("value")
                    if opt_val:
                        await sel.select_option(opt_val)
                        break

        # ── City / location field ──
        city_input = page.locator("input[aria-label*='City'], input[id*='city']")
        if await city_input.count():
            val = await city_input.first.input_value()
            if not val:
                await city_input.first.fill(info["location"])
                await asyncio.sleep(0.8)
                suggestion = page.locator("div[role='option']").first
                if await suggestion.count():
                    await suggestion.click()

        # ── Navigate: Next / Review / Submit ──
        # "Submit application" button
        submit_btn = page.locator("button:has-text('Submit application')")
        if await submit_btn.count() and await submit_btn.is_enabled():
            await submit_btn.click()
            await asyncio.sleep(2)
            return True

        # "Review" button
        review_btn = page.locator("button:has-text('Review')")
        if await review_btn.count() and await review_btn.is_enabled():
            await review_btn.click()
            continue

        # "Next" button
        next_btn = page.locator("button:has-text('Next')")
        if await next_btn.count() and await next_btn.is_enabled():
            await next_btn.click()
            continue

        # If nothing to click, we're stuck
        print(f"  ⚠️  Stuck on step {step + 1} — check browser window")
        break

    return False


async def _apply_easy_apply(job: dict) -> str:
    """Open LinkedIn job page and trigger Easy Apply. Returns 'applied'|'failed'|'unsupported'."""
    async with async_playwright() as p:
        browser, ctx = await _get_browser_context(p)
        page = await ctx.new_page()

        try:
            await page.goto(job["url"], timeout=20000)
            await page.wait_for_load_state("domcontentloaded", timeout=15000)
            await asyncio.sleep(2)

            # Find Easy Apply button
            easy_btn = page.locator(
                "button:has-text('Easy Apply'), "
                "button[aria-label*='Easy Apply']"
            ).first
            if not await easy_btn.count():
                print("  ℹ️  No Easy Apply button — job may require external application")
                await browser.close()
                return "unsupported"

            await easy_btn.click()
            await asyncio.sleep(1.5)

            # Modal should be open now
            modal = page.locator("div[role='dialog']")
            if not await modal.count():
                await browser.close()
                return "failed"

            success = await _handle_easy_apply_modal(page, job)
            await page.screenshot(path=f"/tmp/job_{job['id']}.png")
            await browser.close()
            return "applied" if success else "failed"

        except Exception as e:
            print(f"  Error: {e}")
            try:
                await browser.close()
            except Exception:
                pass
            return "failed"


def apply_to_job(job: dict) -> str:
    return asyncio.run(_apply_easy_apply(job))


# ── Review + apply loop ──────────────────────────────────────────────────────

def run_auto_apply(jobs: list[dict], min_score: int = None) -> dict:
    threshold = min_score or AUTO_APPLY_MIN_SCORE
    results = {"applied": 0, "skipped": 0, "failed": 0, "unsupported": 0}

    eligible = [j for j in jobs if (j.get("score") or 0) >= threshold and j.get("status") == "new"]
    if not eligible:
        print("No eligible jobs for auto-apply.")
        return results

    print(f"\n🤖 Auto-Apply — {len(eligible)} jobs scored {threshold}+\n")

    for job in eligible:
        score = job.get("score", "?")
        title = job.get("title", "")
        company = job.get("company", "")

        print(f"{'─'*60}")
        print(f"  {score}/10  {title} @ {company}")
        print(f"  URL    : {job['url']}")
        print(f"\n  Cover letter preview:")
        cl = (job.get("cover_letter") or "No cover letter generated.")[:400]
        for line in cl.split("\n")[:6]:
            print(f"    {line}")
        print("  ...")

        ans = input("\n  Submit via Easy Apply? [y/n/o=open in browser] → ").strip().lower()

        if ans == "o":
            import webbrowser
            webbrowser.open(job["url"])
            ans = input("  Submit after reviewing? [y/n] → ").strip().lower()

        if ans != "y":
            print("  → Skipped")
            results["skipped"] += 1
            continue

        print("  🚀 Opening Easy Apply...")
        status = apply_to_job(job)
        results[status] += 1

        if status == "applied":
            from tracker import update_status
            update_status(job["id"], "applied")
            print("  ✅ Applied + saved to Supabase")
        elif status == "unsupported":
            from tracker import update_status
            update_status(job["id"], "manual_review")
            print("  📋 Saved to manual queue — run: python main.py manual")
        else:
            print("  ❌ Submit failed — open manually:", job["url"])

        time.sleep(1)

    print(f"\n── Summary ──")
    for k, v in results.items():
        if v:
            print(f"  {k}: {v}")
    return results
