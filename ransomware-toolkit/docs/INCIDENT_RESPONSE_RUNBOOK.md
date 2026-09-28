# Ransomware Incident Response Runbook

For use by clinic staff / the designated IT contact when the dashboard
shows a `critical` alert (canary tampered or mass encryption suspected).

## 0. Before an incident (do this now, not during one)

- [ ] Know who your designated incident lead is and how to reach them
      off-hours.
- [ ] Confirm offline/offsite backups exist and are tested (see
      `scripts/verify_backups.py`).
- [ ] Keep a printed copy of this runbook and key phone numbers — assume
      email and shared drives may be unavailable during an incident.
- [ ] Know your cyber insurance policy number and 24/7 hotline, if you
      have a policy.

## 1. Contain (first 15 minutes)

1. **Do not turn the affected computer off.** Powering off can destroy
   evidence and, for some ransomware, memory-resident decryption keys.
   Instead, disconnect it from the network: unplug the Ethernet cable or
   disable Wi-Fi.
2. If the toolkit's autonomous response is enabled, it may have already
   isolated the host — check the dashboard for an `autonomous_response`
   log entry confirming this.
3. Check the dashboard for **other** endpoints showing alerts. Disconnect
   any additional affected machines the same way.
4. Disconnect shared network drives / NAS from the network if canary
   files on them were tampered with, to stop further spread.
5. Do **not** pay a ransom or contact the attacker before consulting legal
   counsel and (if applicable) your cyber insurer.

## 2. Assess

1. Note which agent_id(s) alerted, the alert type, and timestamp from the
   dashboard — this is your incident timeline start.
2. Identify what data lives on the affected machine(s): does it include
   Protected Health Information (PHI)? This determines HIPAA obligations
   (see `HIPAA_BREACH_CHECKLIST.md`).
3. Check `scripts/verify_backups.py` output / last known-good backup date.

## 3. Notify

1. Notify your designated incident lead / practice manager immediately.
2. If PHI may be involved, start the HIPAA breach assessment checklist in
   parallel — the clock on breach notification timelines starts at
   discovery, not at confirmation.
3. If you have cyber insurance, call the incident hotline before doing
   extensive remediation — many policies require using their approved
   forensics/response vendors to be covered.
4. Consider reporting to the FBI's Internet Crime Complaint Center (IC3)
   and/or your local FBI field office — ransomware against a healthcare
   provider is a federal crime and they may have decryption keys or
   threat intelligence for the specific strain.

## 4. Eradicate & Recover

1. Do not restore from backup onto the same (potentially still infected)
   network until the entry point is identified and closed (patch the
   vulnerability, reset compromised credentials, remove attacker
   persistence).
2. Rebuild affected machines from known-clean images where possible rather
   than trying to "clean" an infected system.
3. Restore data from the most recent backup confirmed clean by
   `verify_backups.py` (i.e., before any entropy/ransom-note issues were
   flagged).
4. Re-enable network access incrementally, watching the dashboard for
   renewed alerts.

## 5. Post-incident

- [ ] Document a timeline: initial alert time, containment time,
      notification times, recovery time.
- [ ] Review whether canary/detection thresholds need tuning.
- [ ] If PHI breach thresholds were met, complete required HHS OCR and
      patient notifications within regulatory deadlines.
- [ ] Rotate credentials that may have been exposed.
- [ ] Debrief: what allowed initial access (phishing, exposed RDP, unpatched
      software)? Close that gap.
