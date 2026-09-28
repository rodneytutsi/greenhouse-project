# HIPAA Breach Assessment Checklist (Ransomware)

This is a working checklist to help a small practice reason through HIPAA
Breach Notification Rule obligations after a ransomware event. **This is
not legal advice** — consult your organization's privacy officer and/or
healthcare compliance counsel; requirements below summarize 45 CFR §§
164.400–414 at a general level and specifics/deadlines should be verified
against current HHS guidance.

## 1. Determine if this is a "breach" of PHI

Under HHS guidance, a ransomware attack that encrypts ePHI is presumed to
be a reportable breach **unless** you can show a low probability that PHI
was compromised, based on a documented risk assessment covering:

- [ ] Nature and extent of PHI involved (types of identifiers, likelihood
      of re-identification).
- [ ] Who the unauthorized actor was / likely was, and their probable
      intent (encryption-only vs. also exfiltrated/viewed data — check
      logs and canary alerts for evidence of exfiltration, not just
      encryption).
- [ ] Whether the PHI was actually acquired or viewed (vs. only
      encrypted in place).
- [ ] The extent to which risk to the PHI has been mitigated (e.g.,
      restored from clean backup, attacker access fully removed).

## 2. If determined to be a reportable breach

- [ ] **Individual notice**: written notice to affected individuals
      without unreasonable delay, generally within 60 days of discovery.
- [ ] **Media notice**: if 500+ residents of a state/jurisdiction are
      affected, notify prominent media in that area within 60 days.
- [ ] **HHS OCR notice**:
      - 500+ individuals affected: notify HHS OCR contemporaneously with
        individual notice (within 60 days).
      - Fewer than 500: log it and submit to HHS OCR annually (within 60
        days of the end of the calendar year).
- [ ] If you are a Business Associate, notify the Covered Entity per your
      Business Associate Agreement (often faster than the 60-day
      individual-notice deadline).

## 3. Documentation to preserve

- [ ] Dashboard alert history (agent_id, timestamps, severity) — export
      from `/api/alerts`.
- [ ] Canary tamper logs and which directories/shares were affected.
- [ ] Backup verification results (`scripts/verify_backups.py` output)
      showing what was/wasn't affected and when clean backups existed.
- [ ] Risk assessment findings and who performed them.
- [ ] Remediation steps taken and completion dates.

## 4. Other obligations to check

- [ ] State breach notification laws (may have stricter/faster timelines
      than HIPAA and apply even if HIPAA's presumption is rebutted).
- [ ] Cyber insurance policy notification deadlines (often much shorter
      than 60 days — check immediately, not after remediation).
- [ ] Contractual notification obligations to partners/vendors.

## 5. Ongoing

- [ ] Update the practice's HIPAA Security Risk Analysis to reflect this
      incident and any new safeguards (including this toolkit).
- [ ] Retrain staff if the entry vector was phishing/social engineering.
