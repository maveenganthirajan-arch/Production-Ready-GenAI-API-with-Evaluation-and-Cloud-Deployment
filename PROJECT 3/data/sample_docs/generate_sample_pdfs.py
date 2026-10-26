import os
from pathlib import Path
from pypdf import PdfReader

def create_pdf(output_path: Path, title: str, pages_data: list):
    """
    Creates a standards-compliant multi-page PDF 1.4 file with fonts, text streams,
    and cross-reference table without external heavy dependencies.
    """
    objects = []
    offsets = []

    def register_object(content_str: str) -> int:
        objects.append(content_str.encode('latin1'))
        return len(objects)

    # Placeholders for catalog (1) and pages parent (2)
    objects.append(b"") # 1: Catalog
    objects.append(b"") # 2: Pages
    # 3: Font
    font_id = 3
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")

    page_refs = []

    for page_num, text_lines in enumerate(pages_data, 1):
        # Build text stream
        stream_cmds = [
            "BT",
            "/F1 16 Tf",
            "50 750 Td",
            f"({title} - Page {page_num}) Tj",
            "/F1 10 Tf",
            "0 -30 Td",
            "14 TL"
        ]
        for line in text_lines:
            safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            # Wrap long lines if needed
            while len(safe) > 85:
                cut = safe[:85].rfind(" ")
                if cut == -1: cut = 85
                stream_cmds.append(f"({safe[:cut]}) '")
                safe = safe[cut:].lstrip()
            stream_cmds.append(f"({safe}) '")
        stream_cmds.append("ET")

        stream_body = "\n".join(stream_cmds).encode('latin1')
        stream_obj_str = f"<< /Length {len(stream_body)} >>\nstream\n".encode('latin1') + stream_body + b"\nendstream"
        
        objects.append(stream_obj_str)
        content_id = len(objects)

        page_obj_str = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
        ).encode('latin1')
        objects.append(page_obj_str)
        page_refs.append(f"{len(objects)} 0 R")

    # Update Catalog and Pages
    objects[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    kids_str = " ".join(page_refs)
    objects[1] = f"<< /Type /Pages /Kids [{kids_str}] /Count {len(page_refs)} >>".encode('latin1')

    # Assemble complete PDF file
    with open(output_path, "wb") as f:
        f.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets.append(0) # object 0

        for i, obj in enumerate(objects, 1):
            offsets.append(f.tell())
            f.write(f"{i} 0 obj\n".encode('latin1'))
            f.write(obj)
            f.write(b"\nendobj\n")

        xref_start = f.tell()
        f.write(f"xref\n0 {len(objects) + 1}\n".encode('latin1'))
        f.write(b"0000000000 65535 f \n")
        for off in offsets[1:]:
            f.write(f"{off:010d} 00000 n \n".encode('latin1'))

        f.write(
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF\n".encode('latin1')
        )

def main():
    base_dir = Path(__file__).resolve().parent

    # 1. HR Policy PDF (2 Pages)
    hr_p1 = [
        "ACME ENTERPRISE - HUMAN RESOURCES POLICY HANDBOOK (2026)",
        "Document Code: HR-POL-2026-V3 | Classification: Internal",
        "--------------------------------------------------------------------------------",
        "1. WORKING HOURS AND REMOTE WORK POLICY",
        "All full-time employees complete 40 hours per week.",
        "Core collaboration hours are 10:00 AM to 4:00 PM local time.",
        "Employees may work remotely up to 4 days per week.",
        "Remote employees receive a one-time home office equipment stipend of $500.",
        "In addition, a monthly internet connectivity reimbursement of $60 is provided.",
        "",
        "2. PAID TIME OFF (PTO) AND ANNUAL LEAVE",
        "Full-time regular employees are entitled to 20 days of paid annual leave per year.",
        "Unused annual leave up to 5 days can be rolled over to the subsequent calendar year.",
        "Rollover days must be utilized before March 31st."
    ]
    hr_p2 = [
        "3. SICK, MEDICAL, AND PARENTAL LEAVES",
        "Employees receive 10 days of paid sick leave per year.",
        "Medical certificates are required for consecutive absences exceeding 3 business days.",
        "Primary caregivers receive 16 weeks of fully paid parental leave.",
        "Secondary caregivers receive 8 weeks of fully paid parental leave.",
        "",
        "4. PERFORMANCE EVALUATIONS AND BONUSES",
        "Performance reviews are held annually during the month of November.",
        "Merit salary adjustments and equity refresh grants take effect on January 1st.",
        "Every regular employee has an annual professional development budget of $1,500.",
        "",
        "5. ETHICS & WHISTLEBLOWER PROTECTION",
        "Confidential 24/7 Ethics Hotline: 1-800-555-ACME or email ethics@acme-corp.internal.",
        "Whistleblowers are strictly protected from retaliation under company policy."
    ]
    create_pdf(base_dir / "HR_Policy_Handbook.pdf", "HR Policy Handbook", [hr_p1, hr_p2])

    # 2. Cloud Infrastructure Security Manual PDF (2 Pages)
    sec_p1 = [
        "ACME ENTERPRISE - CLOUD INFRASTRUCTURE & SECURITY MANUAL",
        "Document Code: SEC-OPS-2026-V4 | Classification: Confidential",
        "--------------------------------------------------------------------------------",
        "1. CLOUD ARCHITECTURE AND COMPLIANCE",
        "Production workloads are deployed across AWS us-east-1 and us-west-2 multi-AZ.",
        "Direct public routing to database tiers is strictly prohibited.",
        "East-west Kubernetes pod traffic enforces Mutual TLS (mTLS) via Istio service mesh.",
        "",
        "2. IDENTITY AND ACCESS MANAGEMENT (IAM) & PASSWORDS",
        "Corporate systems enforce a mandatory 90-day password rotation schedule.",
        "Passwords must contain at least 14 characters with uppercase, lowercase, numbers, and symbols.",
        "Hardware FIDO2 WebAuthn or approved authenticator apps are required for MFA.",
        "SMS-based 2FA is prohibited due to SIM-swapping risks."
    ]
    sec_p2 = [
        "3. API TOKENS AND SECRET MANAGEMENT",
        "API tokens and secrets must be stored in HashiCorp Vault or AWS Secrets Manager.",
        "Programmatic service tokens automatically expire every 30 days.",
        "",
        "4. INCIDENT RESPONSE & ESCALATION PROTOCOLS",
        "Severity 1 (Critical): Active data breach or complete production outage.",
        "Severity 1 incidents require response from incident commander within 15 minutes.",
        "Public status updates must be posted on status.acme-corp.com within 45 minutes.",
        "",
        "5. BACKUP, DISASTER RECOVERY, AND CONTINUITY",
        "Databases enforce Recovery Point Objective (RPO) under 1 hour.",
        "Recovery Time Objective (RTO) is strictly under 4 hours.",
        "Automated encrypted snapshots are replicated across regions every 6 hours."
    ]
    create_pdf(base_dir / "Cloud_Infrastructure_Security_Manual.pdf", "Cloud Security Manual", [sec_p1, sec_p2])

    # 3. Financial Performance Report PDF (1 Page)
    fin_p1 = [
        "ACME ENTERPRISE CORP - Q3 FINANCIAL PERFORMANCE REPORT",
        "Document Code: FIN-REP-2026-Q3 | Audience: Executive Board",
        "--------------------------------------------------------------------------------",
        "1. EXECUTIVE SUMMARY & REVENUE HIGHLIGHTS",
        "Total Q3 Revenue reached $48.5 million, a 24% year-over-year increase.",
        "Annual Recurring Revenue (ARR) grew to $184.2 million (+28% YoY).",
        "Net Retention Rate (NRR) reached 118%.",
        "GAAP Net Profit Margin expanded to 19.4% (up from 14.2% in Q3 2025).",
        "Free cash flow generated during Q3 was $12.8 million.",
        "",
        "2. DEPARTMENTAL BUDGET ALLOCATIONS",
        "Research & Development (R&D) was allocated $18.2 million (57.8% of operating budget).",
        "Sales & Marketing (S&M) was allocated $14.1 million.",
        "General & Administrative (G&A) was allocated $6.2 million.",
        "",
        "3. CLIENT METRICS AND Q4 OUTLOOK",
        "Total enterprise client portfolio expanded to 312 organizations with 42 new accounts.",
        "Average Contract Value (ACV) increased to $155,000 annually.",
        "Quarterly churn rate declined to 1.2%.",
        "Q4 2026 revenue target is set between $51.0 million and $53.0 million."
    ]
    create_pdf(base_dir / "Q3_Financial_Performance_Report.pdf", "Q3 Financial Report", [fin_p1])

    print("Sample PDFs successfully created:")
    for pdf_name in ["HR_Policy_Handbook.pdf", "Cloud_Infrastructure_Security_Manual.pdf", "Q3_Financial_Performance_Report.pdf"]:
        pdf_path = base_dir / pdf_name
        reader = PdfReader(str(pdf_path))
        print(f" - {pdf_name}: {len(reader.pages)} pages, {pdf_path.stat().st_size} bytes")

if __name__ == "__main__":
    main()
