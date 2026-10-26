import ipaddress
import re
import socket
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

from friday.domain.models import (
    BrowserAction,
    BrowserActionAssessment,
    BrowserActionType,
    BrowserCompletionEvidence,
    VerificationResult,
)


class BrowserPolicy:
    def __init__(self, allowed_domains: set[str], upload_root: Path) -> None:
        self.allowed_domains = {domain.casefold() for domain in allowed_domains}
        self.upload_root = upload_root.resolve()
        self.submission_keys: set[str] = set()

    def assess(self, action: BrowserAction) -> BrowserActionAssessment:
        parsed = urlparse(action.url)
        if parsed.scheme not in {"https", "http"} or not parsed.hostname:
            return BrowserActionAssessment(
                allowed=False, requires_approval=False, reason="URL must use HTTP or HTTPS"
            )
        host = parsed.hostname.casefold()
        if host not in self.allowed_domains and not any(
            host.endswith("." + domain) for domain in self.allowed_domains
        ):
            return BrowserActionAssessment(
                allowed=False, requires_approval=False, reason="Domain is not allowlisted"
            )
        if self._is_private_host(host):
            return BrowserActionAssessment(
                allowed=False, requires_approval=False, reason="Private-network navigation is blocked"
            )
        if action.action_type == BrowserActionType.SUBMIT:
            if not action.idempotency_key:
                return BrowserActionAssessment(
                    allowed=False,
                    requires_approval=True,
                    reason="Submission requires an idempotency key",
                )
            if action.idempotency_key in self.submission_keys:
                return BrowserActionAssessment(
                    allowed=False,
                    requires_approval=True,
                    reason="Duplicate submission is blocked",
                )
            return BrowserActionAssessment(
                allowed=False,
                requires_approval=True,
                reason="Sensitive form submission requires explicit approval",
            )
        return BrowserActionAssessment(
            allowed=True, requires_approval=False, reason="Deterministic browser action is allowed"
        )

    def register_approved_submission(self, idempotency_key: str) -> None:
        if idempotency_key in self.submission_keys:
            raise ValueError("Duplicate submission is blocked")
        self.submission_keys.add(idempotency_key)

    def validate_upload(self, file_path: str | Path) -> Path:
        original = Path(file_path)
        if original.is_symlink():
            raise PermissionError("Symlink uploads are not allowed")
        path = original.resolve()
        if path != self.upload_root and self.upload_root not in path.parents:
            raise PermissionError("Upload file is outside the approved manifest root")
        return path

    @staticmethod
    def captcha_assessment() -> BrowserActionAssessment:
        return BrowserActionAssessment(
            allowed=False,
            requires_approval=False,
            requires_manual_intervention=True,
            reason="CAPTCHA requires manual intervention",
        )

    @staticmethod
    def verify_completion(evidence: BrowserCompletionEvidence) -> VerificationResult:
        if evidence.action_type != BrowserActionType.SUBMIT:
            return VerificationResult(
                verified=bool(evidence.provider_state),
                outcome="completed" if evidence.provider_state else "unverified",
                missing_evidence=[] if evidence.provider_state else ["resulting state"],
            )
        confirmed = bool(
            evidence.confirmation_number
            or evidence.provider_state
            or (evidence.confirmation_url and "confirm" in evidence.confirmation_url.casefold())
        )
        return VerificationResult(
            verified=confirmed,
            outcome="completed" if confirmed else "unverified",
            missing_evidence=[] if confirmed else ["confirmation page, number, or provider state"],
        )

    @staticmethod
    def _is_private_host(host: str) -> bool:
        if host in {"localhost", "localhost.localdomain"}:
            return True
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(host, None)}
        except socket.gaierror:
            return True
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return True
        return False


class ChromeFormWorker:
    """Deterministic Chrome form worker; never handles passwords, payment data, or CAPTCHAs."""

    SAFE_FIELD = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,79}$")
    BLOCKED_TYPES = {"password", "file", "hidden"}
    BLOCKED_HINTS = {"password", "passcode", "credit", "card", "cvv", "cvc", "ssn"}

    def __init__(
        self,
        policy: BrowserPolicy,
        profile_dir: Path,
        evidence_dir: Path,
        chrome_path: Path = Path(
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        ),
        headless: bool = False,
    ) -> None:
        self.policy = policy
        self.profile_dir = profile_dir.resolve()
        self.evidence_dir = evidence_dir.resolve()
        self.chrome_path = chrome_path
        self.headless = headless
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)

    async def fill_preview(
        self,
        url: str,
        fields: dict[str, str],
        evidence_name: str,
        submit_selector: str | None = None,
    ) -> dict[str, object]:
        assessment = self.policy.assess(
            BrowserAction(action_type=BrowserActionType.NAVIGATE, url=url)
        )
        if not assessment.allowed:
            raise PermissionError(assessment.reason)
        if not self.chrome_path.exists():
            raise RuntimeError("Google Chrome is not installed")
        for key, value in fields.items():
            if not self.SAFE_FIELD.fullmatch(key):
                raise ValueError(f"Unsafe form field name: {key}")
            lowered = f"{key} {value[:40]}".casefold()
            if any(hint in lowered for hint in self.BLOCKED_HINTS):
                raise PermissionError("Sensitive credential or payment fields are blocked")
        screenshot = self.evidence_dir / f"{evidence_name}.png"
        async with async_playwright() as playwright:
            context = await playwright.chromium.launch_persistent_context(
                str(self.profile_dir),
                executable_path=str(self.chrome_path),
                headless=self.headless,
                args=["--no-first-run", "--no-default-browser-check"],
            )
            try:
                page = context.pages[0] if context.pages else await context.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                page_text = (await page.locator("body").inner_text(timeout=5_000)).casefold()
                if "captcha" in page_text or "verify you are human" in page_text:
                    raise RuntimeError("CAPTCHA requires manual intervention")
                filled: dict[str, str] = {}
                for key, value in fields.items():
                    locator = page.locator(f'[name="{key}"]')
                    if await locator.count() != 1:
                        raise ValueError(f"Expected exactly one field named {key}")
                    field_type = (await locator.get_attribute("type") or "text").casefold()
                    if field_type in self.BLOCKED_TYPES:
                        raise PermissionError(f"Field type {field_type} is blocked")
                    await locator.fill(value)
                    filled[key] = value
                await page.screenshot(path=str(screenshot), full_page=True)
                submitted = False
                confirmation_detected = False
                resulting_url = page.url
                if submit_selector:
                    submit = page.locator(submit_selector)
                    if await submit.count() != 1:
                        raise ValueError("Submit selector must match exactly one control")
                    await submit.click()
                    await page.wait_for_load_state("domcontentloaded", timeout=15_000)
                    submitted = True
                    resulting_url = page.url
                    confirmation_text = (
                        await page.locator("body").inner_text(timeout=5_000)
                    ).casefold()
                    confirmation_detected = any(
                        marker in confirmation_text
                        for marker in ("thank you", "submitted", "confirmation", "application received")
                    )
                    await page.screenshot(path=str(screenshot), full_page=True)
                return {
                    "url": url,
                    "resulting_url": resulting_url,
                    "filled_fields": filled,
                    "submitted": submitted,
                    "confirmation_detected": confirmation_detected,
                    "screenshot_path": str(screenshot),
                }
            finally:
                await context.close()

    async def read_page(self, url: str) -> dict[str, object]:
        assessment = self.policy.assess(BrowserAction(action_type=BrowserActionType.NAVIGATE, url=url))
        if not assessment.allowed:
            raise PermissionError(assessment.reason)
        if not self.chrome_path.exists():
            raise RuntimeError("Google Chrome is not installed")
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(executable_path=str(self.chrome_path), headless=True)
            try:
                page = await browser.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                text = await page.locator("body").inner_text(timeout=5_000)
                if "captcha" in text.casefold() or "verify you are human" in text.casefold():
                    raise RuntimeError("CAPTCHA requires manual intervention")
                return {"url": page.url, "title": await page.title(), "text": text[:50_000]}
            finally:
                await browser.close()
