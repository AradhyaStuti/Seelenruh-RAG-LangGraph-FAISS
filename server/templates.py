"""Legal document templates. Plain-Python builders — no Jinja, no LLM, no surprises."""
from datetime import date
from typing import Callable


def _val(fields: dict, key: str, fallback: str = "____") -> str:
    v = fields.get(key)
    if v is None or (isinstance(v, str) and not v.strip()):
        return fallback
    return str(v).strip()


def _today() -> str:
    return date.today().strftime("%d %B %Y")


def rti_application(fields: dict) -> dict:
    name = _val(fields, "applicantName")
    address = _val(fields, "applicantAddress")
    phone = _val(fields, "applicantPhone", "")
    authority = _val(fields, "publicAuthority")
    pio_address = _val(fields, "pioAddress", "Public Information Officer")
    info_sought = _val(fields, "informationSought", "[describe the information you need]")
    period = _val(fields, "period", "")
    bpl = bool(fields.get("isBpl"))

    period_line = f"Period: {period}\n" if period and period != "____" else ""

    body = f"""To,
The Public Information Officer
{authority}
{pio_address}

Subject: Application under the Right to Information Act, 2005

Sir / Madam,

Under Section 6(1) of the Right to Information Act, 2005, I request the following information held by your public authority:

{info_sought}

{period_line}I undertake to pay the prescribed fee. {'Being a person below the poverty line I am exempt from the fee under Section 7(5); a copy of my BPL certificate is enclosed.' if bpl else 'A fee of ₹10 by Indian Postal Order in favour of the Accounts Officer of your department is enclosed.'}

Kindly furnish the information within 30 days as mandated by Section 7(1) of the Act. If any part of this information is held by another public authority, please transfer the request under Section 6(3) and inform me of the transfer.

If this request is denied in whole or in part, please cite the specific provisions of the Act on which the denial is based.

Yours faithfully,

{name}
{address}
{('Phone: ' + phone) if phone else ''}

Date: {_today()}
Place: ____
"""
    return {
        "title": f"RTI Application — {authority}",
        "body": body.strip() + "\n",
        "notes": [
            "Write your specific question precisely — vague questions get vague answers or denials.",
            "Address it to the PIO of the right public authority; you can search rtionline.gov.in for the central list.",
            "Fee: ₹10 via Indian Postal Order (IPO) for central authorities, state rules vary. BPL applicants are exempt.",
            "First appeal lies with the First Appellate Authority within 30 days of refusal / non-reply.",
        ],
    }


def consumer_complaint(fields: dict) -> dict:
    name = _val(fields, "complainantName")
    address = _val(fields, "complainantAddress")
    phone = _val(fields, "complainantPhone", "")
    opposite = _val(fields, "opposingParty")
    opposite_address = _val(fields, "opposingPartyAddress", "")
    purchase = _val(fields, "purchaseDate", "____")
    amount = _val(fields, "amountPaid", "____")
    grievance = _val(fields, "grievance", "[describe the defect / deficiency / unfair trade practice]")
    relief = _val(fields, "reliefSought", "refund, replacement and compensation as the Hon'ble Commission deems fit")

    try:
        amt = float(str(amount).replace(",", ""))
        if amt <= 50 * 100_000:
            jurisdiction = "District Consumer Disputes Redressal Commission"
        elif amt <= 2 * 100 * 100_000:
            jurisdiction = "State Consumer Disputes Redressal Commission"
        else:
            jurisdiction = "National Consumer Disputes Redressal Commission"
    except ValueError:
        jurisdiction = "District Consumer Disputes Redressal Commission"

    body = f"""BEFORE THE {jurisdiction.upper()}

In the matter of:

{name}
{address}
{('Phone: ' + phone) if phone else ''}
                                                        ... Complainant

                            Versus

{opposite}
{opposite_address}
                                                        ... Opposite Party

COMPLAINT UNDER SECTION 35 OF THE CONSUMER PROTECTION ACT, 2019

Most respectfully showeth:

1. That the Complainant is a "consumer" within the meaning of Section 2(7) of the Consumer Protection Act, 2019.

2. That on {purchase}, the Complainant purchased / availed services from the Opposite Party for a sum of ₹{amount}. Copies of the invoice / receipt are enclosed and marked as Annexure A.

3. That the cause of action arose as follows:

{grievance}

4. That despite repeated requests the Opposite Party has failed to redress the grievance, amounting to a "deficiency in service" / "defect in goods" / "unfair trade practice" under Sections 2(11), 2(10) and 2(47) of the Act.

5. That this Hon'ble Commission has territorial and pecuniary jurisdiction under Section 34 read with Section 35 of the Act.

6. That the cause of action is within the limitation period of two years prescribed under Section 69 of the Act.

PRAYER

The Complainant therefore prays that this Hon'ble Commission may be pleased to:
(a) {relief};
(b) award costs of these proceedings;
(c) grant such further relief as is just and equitable in the circumstances.

{name}
Complainant
Through:

Date: {_today()}
Place: ____

VERIFICATION
I, {name}, the Complainant herein, do hereby verify that the contents of paragraphs 1–6 above are true to my knowledge and belief, and nothing material has been concealed therefrom.

Verified at ____ on {_today()}.

{name}
"""
    return {
        "title": f"Consumer Complaint — vs {opposite}",
        "body": body.strip() + "\n",
        "notes": [
            f"Jurisdiction picked by claim value: {jurisdiction}.",
            "File via the E-Daakhil portal (edaakhil.nic.in) for a fully online filing — saves the District Commission visit.",
            "Attach: invoice / receipt, correspondence with the seller, any warranty card, proof of identity.",
            "Limitation: 2 years from the cause of action under Section 69 of the Act.",
        ],
    }


def rent_notice(fields: dict) -> dict:
    sender = _val(fields, "senderName")
    sender_address = _val(fields, "senderAddress")
    tenant = _val(fields, "tenantName")
    property_address = _val(fields, "propertyAddress")
    monthly_rent = _val(fields, "monthlyRent", "____")
    rent_due = _val(fields, "rentDueAmount", "____")
    months_due = _val(fields, "monthsDue", "____")
    notice_period = _val(fields, "noticePeriodDays", "15")
    reason = _val(fields, "reason", "non-payment of rent")

    body = f"""LEGAL NOTICE TO QUIT AND DELIVER VACANT POSSESSION
(Under Section 106 of the Transfer of Property Act, 1882)

To,
{tenant}
Tenant of the premises at:
{property_address}

From,
{sender}
{sender_address}

Date: {_today()}

Sir / Madam,

Under instructions and on behalf of my client, I serve you with the following notice:

1. You have been the tenant of the premises described above on a month-to-month tenancy at a monthly rent of ₹{monthly_rent}.

2. The cause for this notice is {reason}. As of the date hereof an amount of ₹{rent_due} representing rent for {months_due} month(s) remains outstanding despite repeated demands.

3. By this notice and in exercise of the rights conferred by Section 106 of the Transfer of Property Act, 1882, your tenancy in respect of the above premises is hereby terminated with effect from the expiry of {notice_period} days from the date of receipt of this notice.

4. You are called upon to (a) pay the entire arrears of rent of ₹{rent_due} together with mesne profits and (b) hand over vacant peaceful possession of the premises to the undersigned on or before the expiry of the said {notice_period}-day period.

5. Please take notice that on your failure to comply with the above, my client shall be constrained to initiate appropriate civil proceedings for eviction and recovery of arrears at your sole risk as to costs and consequences, which kindly note.

6. A copy of this notice has been retained in my office for record and further necessary action.

{sender}
"""
    return {
        "title": f"Rent / Quit Notice — {tenant}",
        "body": body.strip() + "\n",
        "notes": [
            "Send by registered post with acknowledgement due (Reg-AD) AND keep the postal receipt + tracking proof.",
            "15 days is the statutory minimum under Section 106 TPA for a monthly tenancy; longer if the lease deed says so.",
            "Self-help eviction (changing locks, cutting utilities) is criminal trespass under IPC §441 — file a civil suit instead.",
            "If the tenant pays within the notice period, the cause is satisfied and the eviction part of the notice is spent.",
        ],
    }


BUILDERS: dict[str, Callable[[dict], dict]] = {
    "rti": rti_application,
    "consumer_complaint": consumer_complaint,
    "rent_notice": rent_notice,
}


def build(kind: str, fields: dict) -> dict:
    builder = BUILDERS.get(kind)
    if not builder:
        raise ValueError(f"Unknown template kind: {kind}")
    return builder(fields or {})
