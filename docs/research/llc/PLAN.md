# Forming an LLC: plan

CONFIDENTIAL to greg. Prepared 2026-10-22 in the symphony_2 thread "Forming an LLC". Not legal advice: every item marked LAWYER is a question for an attorney of greg's own (not Wayne State's counsel, who represents the university). Nothing here is filed, paid or signed; every binding step is greg's hand.

Defaults used until greg answers: name OpenSpine Consortium LLC, one member (greg), member-managed, Michigan, purpose "develop, license and sell software and medical imaging technology, and take licences of university-owned technology".

## 1. What the LLC can hold, under Wayne State's own rules

Source: Board of Governors Statute 2.41.04, Patent and Copyright Policy (https://bog.wayne.edu/code/2-41-04, read 2026-10-22; adopted 1969, amended 1984).

- **Copyright stays with faculty.** The statute's copyright section says faculty and staff "retain all rights to copyright in published works". The patent policy "applies only to patentable inventions". Software is not named. So the copyright in Symphony's code, which greg wrote (with Claude) and published under MIT, reads as greg's, and he can assign it to the LLC. The exception is a work the university directed him to produce within his employment; nobody did. LAWYER: confirm that published, self-directed software falls under "published works" and that greg's employment contract or the Medical School's bylaws add nothing (some clinical departments have their own IP terms).
- **Patentable inventions depend on university support.** The inventor owns an invention made (1) without university support, or (2) without university funds (salary excepted), facilities, equipment or services and (3) free of any sponsor's terms. Otherwise WSU has the right of first refusal to title, must decide within four months whether to take or waive it, and may waive.
  - **SchwingNet (disclosure 26-1902)** used the WSU grid, WSU-held data under WSU IRB protocols and possibly the AIDaS grant, so WSU very likely holds the first right. The routes that leave greg in control: (a) ask WSU to waive (the statute allows it); (b) take an exclusive licence to the LLC from WSU (the normal faculty-startup route; WSU did exactly this for Mitovation, Inc. in October 2024); (c) if WSU takes title and fails to license within 24 months of the patent issuing, ownership passes to the inventor under the statute's licensing section. Inventor's royalty share if WSU licenses to anyone: 75% of the first $10,000 net, falling to 35% above $1 million.
  - **Symphony's patentable mechanisms** (the patentability memo, patent/symphony/) were built on greg's own accounts but touched the WSU grid (grid.yml through Beethoven) and the WSU Microsoft tenant (Folders). Whether that is "use of facilities or services" decides who owns any patent. LAWYER and WSU Technology Commercialization: one short conversation, kept separate from 26-1902. The copyright point above holds either way.
- **The LLC cannot simply receive disclosed IP.** Assigning 26-1902 material to the LLC without WSU's agreement would breach the statute and the University Patent Agreement greg signed, and could cloud the provisional. Do not copy SchwingNet code into any LLC repository until the licence or waiver is signed.
- **Conflict of interest.** A WSU contract with a company in which an employee holds a financial interest needs disclosure to the Board of Governors and approval in open session by two thirds of the Board (Michigan conflict-of-interest law, as the Board's Mitovation item of 2024-10-24 records, https://bog.wayne.edu/meetings/390/23-24-oct-2024-bog-agenda-item-viiic.pdf). Plan on it for any WSU licence to the LLC. Also disclose the LLC in greg's annual conflict-of-interest and outside-activity filing. LAWYER: whether the outside-activity rules for clinical faculty limit time or income from the LLC.
- **Consulting waiver does not apply.** The statute's waiver for consulting is refused where the faculty member is a stockholder or officer of the company, which greg would be.

## 2. Which state

| | Michigan | Delaware | Wyoming |
|---|---|---|---|
| Filing | $50 (Articles of Organization, CSCL/CD-700) | $110 | $100 |
| Yearly | $25 annual statement, due 15 February (none the first February when formed after 30 September) | $300 annual tax | $60 minimum |
| Registered agent | greg himself at a Michigan address, free | paid agent required, about $50 to $300 a year | paid agent required |
| Also register in Michigan? | no | yes, as a foreign LLC, plus Michigan's yearly fee | yes, same |

Recommendation: Michigan. greg lives and works there, so any other state adds a second set of fees and filings. Delaware matters only for venture investors, who will ask for a Delaware C-corporation anyway; an LLC converts later (LAWYER, if fundraising is in view). Wyoming's privacy is lost once the LLC registers in Michigan.

## 3. Steps, in order

1. Answer the four questions (name, members, purpose, state).
2. Check the name: Michigan Business Entity Search, https://www.michigan.gov/corpentitysearch, and the federal trademark search, https://tmsearch.uspto.gov. The patentability memo already flags "Symphony" as a crowded mark; a company name built on OpenSpine avoids that.
3. File the Articles of Organization online: https://www.michigan.gov/corpfileonline (MiBusiness Registry, sign in with MiLogin for Business). Fee $50 by card. Registered agent: greg, or a commercial agent if he would rather not have his home address on the public record. LAWYER optional.
4. Get an EIN from the IRS, free, online: https://www.irs.gov/businesses/small-businesses-self-employed/get-an-employer-identification-number . A single-member LLC is taxed as a sole proprietorship by default (Schedule C) unless it elects otherwise; CPA question whether an S-corporation election is ever worth it.
5. Sign the operating agreement (llc/OPERATING_AGREEMENT.md, a draft). Michigan does not file it, but banks and WSU will ask.
6. Open a business bank account in the LLC's name with the Articles, the EIN letter and the operating agreement. Keep the LLC's money separate from greg's, or the liability shield weakens.
7. Assign to the LLC, by a short signed assignment, only what is clearly greg's: the copyright in Symphony's code and sites, the OpenSpine names and domain, and the GitHub organization's ownership if wanted. LAWYER drafts or reviews it.
8. Disclose the LLC to Wayne State (conflict-of-interest filing) and open the licence conversation with Technology Commercialization for 26-1902 and any Symphony patent.
9. Michigan sales or use tax registration only if the LLC sells taxable goods or services in Michigan (CPA question). Federal BOI reporting: FinCEN's March 2025 rule exempts US-formed companies, so nothing is due unless that changes.
10. Calendar: Michigan annual statement every 15 February; the provisional's 12-month deadline.

## 4. Lawyer questions, one list

1. Does published, self-directed software fall under the statute's faculty copyright, and does any Medical School or departmental term change that?
2. Does using the WSU grid and tenant make Symphony's patentable mechanisms "university supported"?
3. Waiver or exclusive licence for 26-1902, and the terms to ask for (field, equity, royalties, patent cost reimbursement).
4. Outside-activity limits for clinical faculty on time and income from the LLC.
5. Whether to form as an LLC now and convert later, or as a Delaware C-corporation, if outside investment is planned.
6. Review of the assignment in step 7 and the operating agreement.
