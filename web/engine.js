/* Rules engine: JavaScript port of property_agent/ (rules.py, calculator.py, advisor.py).
 * Keep the numbers in sync with property_agent/rules.py when policy changes. */
/* ================= Rules (mirror of property_agent/rules.py) ================= */
const R = {
  POLICY_AS_OF: "2026-10",
  BSD_TIERS: [[180000,.01],[180000,.02],[640000,.03],[500000,.04],[1500000,.05],[Infinity,.06]],
  ABSD: { SC:{1:0,2:.2,3:.3}, PR:{1:.05,2:.3,3:.35}, FOREIGNER:{1:.6,2:.6,3:.6} },
  TDSR:.55, MSR:.30, STRESS:.04, HDB_RATE:.026,
  BANK_LTV:{1:.75,2:.45,3:.35}, BANK_MIN_CASH:{1:.05,2:.25,3:.25},
  HDB_LTV:.75, HDB_INC_CEIL:14000, HDB_INC_CEIL_SINGLE:7000,
  TENURE_BANK:30, TENURE_HDB:25, END_AGE:65,
  EC_CEIL:16000, MOP:5, PRIV_TO_HDB_M:15, PRIV_TO_EC_M:30, SINGLE_MIN_AGE:35,
  FEES:5000, SELL_COST:.02, MARKET_RATE:.028,
  BANDS: {
    HDB_RESALE:{entry:450000,typical:700000,note:"3-room from ~$450k; 4-room ~$600k-$900k; 5-room ~$700k-$1.1M"},
    EC_NEW_LAUNCH:{entry:1300000,typical:1600000,note:"~$1,700-$1,900 psf; 3BR ~$1.5M-$1.7M, 4BR ~$1.9M+"},
    PRIVATE_RESALE:{entry:900000,typical:1500000,note:"OCR 2-3BR ~$1.2M-$1.8M; older/smaller units from ~$900k"},
    PRIVATE_NEW_LAUNCH:{entry:1200000,typical:1900000,note:"OCR ~$2,200-$2,500 psf; 2BR ~$1.4M, 3BR ~$2.0M+"},
    LANDED:{entry:2800000,typical:4000000,note:"Leasehold terrace from ~$2.8M; freehold terrace ~$3.5M-$5M; semi-D $5M+"},
  },
};
const LABELS = { HDB_RESALE:"HDB Resale", EC_NEW_LAUNCH:"New Launch EC", PRIVATE_RESALE:"Resale Private Condo", PRIVATE_NEW_LAUNCH:"New Launch Private Condo", LANDED:"Landed" };

/* ================= Profile ================= */
const RES_ALIAS = { SINGAPOREAN:"SC", CITIZEN:"SC", SG:"SC", "SINGAPORE CITIZEN":"SC", "PERMANENT RESIDENT":"PR", SPR:"PR", FOREIGN:"FOREIGNER", OTHER:"FOREIGNER" };
function res(v, name) {
  if (v == null || v === "") return null;
  let s = String(v).trim().toUpperCase(); s = RES_ALIAS[s] || s;
  if (!["SC","PR","FOREIGNER"].includes(s)) throw new Error(`${name} must be SC, PR or FOREIGNER`);
  return s;
}
function num(v, name, def = 0) {
  if (v == null || v === "") return def;
  const n = Number(String(v).replace(/[,$]/g, ""));
  if (!isFinite(n) || n < 0) throw new Error(`${name} must be a non-negative number`);
  return n;
}
function pick(v, opts, name, def) {
  if (v == null || v === "") return def;
  const s = String(v).trim().toLowerCase();
  if (!opts.includes(s)) throw new Error(`${name} must be one of ${opts.join(", ")}`);
  return s;
}
function makeProfile(d) {
  for (const k of ["residency","age","monthly_income"]) if (d[k] == null || d[k] === "") throw new Error(`missing required field: ${k}`);
  const age = Math.round(num(d.age, "age"));
  if (age < 21 || age > 99) throw new Error("age must be between 21 and 99");
  let household = pick(d.household_type, ["single","married_couple","other_joint"], "household_type", "single");
  const co = res(d.co_applicant_residency, "co_applicant_residency");
  if (household === "single" && co) household = "other_joint";
  let cp = null;
  if (d.current_property && d.current_property.type) {
    const c = d.current_property, t = String(c.type).toUpperCase();
    if (!["HDB","EC","PRIVATE","LANDED"].includes(t)) throw new Error("current_property.type must be HDB, EC, PRIVATE or LANDED");
    cp = { type:t, value:num(c.estimated_value,"estimated_value"), loan:num(c.outstanding_loan,"outstanding_loan"),
           cpfUsed:num(c.cpf_used_with_interest,"cpf_used_with_interest"), years:num(c.years_owned,"years_owned"),
           plan:pick(c.plan,["sell","keep"],"plan","sell") };
  }
  const p = {
    residency: res(d.residency, "residency"), co, household, age,
    income: num(d.monthly_income, "monthly_income"), debt: num(d.existing_monthly_debt, "existing_monthly_debt"),
    cpf: num(d.cpf_oa_balance, "cpf_oa_balance"), cash: num(d.cash_savings, "cash_savings"), cp,
    others: Math.round(num(d.other_properties_count, "other_properties_count")),
    purpose: pick(d.purpose, ["own_stay","investment"], "purpose", "own_stay"),
    timeline: pick(d.timeline, ["immediate","flexible"], "timeline", "flexible"),
    sinceDisposed: d.years_since_disposed_private == null || d.years_since_disposed_private === "" ? null : num(d.years_since_disposed_private, "years_since_disposed_private"),
  };
  p.buyers = [p.residency, p.co].filter(Boolean);
  p.hasSC = p.buyers.includes("SC");
  p.isFamily = (p.household === "married_couple" || p.household === "other_joint") && p.buyers.length >= 2;
  p.keeps = !!cp && cp.plan === "keep";
  p.sells = !!cp && cp.plan === "sell";
  p.ownsPrivate = (!!cp && (cp.type === "PRIVATE" || cp.type === "LANDED")) || p.others > 0;
  const order = { SC:0, PR:1, FOREIGNER:2 };
  p.absdRes = (p.household === "married_couple" && p.hasSC) ? "SC" : p.buyers.reduce((a, b) => order[b] > order[a] ? b : a);
  p.propsAfter = Math.min(p.others + (p.keeps ? 1 : 0) + 1, 3);
  p.loansAfter = Math.min((p.keeps && cp.loan > 0 ? 1 : 0) + 1, 3);
  return p;
}

/* ================= Calculator ================= */
function bsd(price) { let d = 0, rem = price; for (const [size, rate] of R.BSD_TIERS) { const part = Math.min(rem, size); d += part * rate; rem -= part; if (rem <= 0) break; } return d; }
const absdRate = (r, n) => R.ABSD[r][Math.min(Math.max(n, 1), 3)];
function instalment(loan, rate, yrs) { if (loan <= 0) return 0; const r = rate / 12, n = yrs * 12; return loan * r / (1 - Math.pow(1 + r, -n)); }
function loanFrom(inst, rate, yrs) { if (inst <= 0) return 0; const r = rate / 12, n = yrs * 12; return inst * (1 - Math.pow(1 + r, -n)) / r; }
function funds(p) {
  let cpf = p.cpf, cash = p.cash, proceeds = 0, refund = 0;
  if (p.cp && p.cp.plan === "sell") {
    const gross = p.cp.value * (1 - R.SELL_COST) - p.cp.loan;
    proceeds = Math.max(gross - p.cp.cpfUsed, 0);
    refund = Math.min(p.cp.cpfUsed, Math.max(gross, 0));
  }
  return { cpf: cpf + refund, cash: cash + proceeds, sale_cash_proceeds: proceeds, cpf_refund_from_sale: refund };
}
const hdbLoanOk = p => p.hasSC && p.income <= (p.isFamily ? R.HDB_INC_CEIL : R.HDB_INC_CEIL_SINGLE) && !p.ownsPrivate;
function financing(p, seg) {
  const msr = seg === "HDB_RESALE" || seg === "EC_NEW_LAUNCH";
  const tenure = Math.max(5, Math.min(R.TENURE_BANK, R.END_AGE - p.age));
  const opts = [{ name:"bank", ltv:R.BANK_LTV[p.loansAfter], minCash:R.BANK_MIN_CASH[p.loansAfter], tenure, rate:R.STRESS, msr }];
  if (seg === "HDB_RESALE" && hdbLoanOk(p)) opts.push({ name:"hdb_loan", ltv:R.HDB_LTV, minCash:0, tenure:Math.max(5, Math.min(R.TENURE_HDB, R.END_AGE - p.age)), rate:R.HDB_RATE, msr:true });
  return opts;
}
function maxLoanByIncome(p, f) {
  let room = p.income * R.TDSR - p.debt;
  if (f.msr) room = Math.min(room, p.income * R.MSR);
  return loanFrom(Math.max(room, 0), f.rate, f.tenure);
}
function check(price, p, f, fu, incLoan) {
  const loan = Math.min(price * f.ltv, incLoan), b = bsd(price), a = price * absdRate(p.absdRes, p.propsAfter);
  if (fu.cash < price * f.minCash) return [false, "minimum cash downpayment", loan, b, a];
  if (fu.cash + fu.cpf < price - loan + b + a + R.FEES) return [false, loan < price * f.ltv ? "loan limit (income / TDSR-MSR)" : "downpayment + stamp duties (cash/CPF)", loan, b, a];
  return [true, "", loan, b, a];
}
function maxPrice(p, seg, fu) {
  let best = null;
  for (const f of financing(p, seg)) {
    const incLoan = maxLoanByIncome(p, f);
    let lo = 0, hi = 2e7, why = "funds";
    for (let i = 0; i < 60; i++) { const mid = (lo + hi) / 2; const c = check(mid, p, f, fu, incLoan); if (c[0]) lo = mid; else { hi = mid; why = c[1]; } }
    const price = Math.round(lo / 1000) * 1000; const c = check(price, p, f, fu, incLoan);
    const r = { max_price:price, financing:f.name, loan_amount:Math.round(c[2]), max_loan_by_income:Math.round(incLoan), ltv:f.ltv, tenure_years:f.tenure,
                bsd:Math.round(c[3]), absd:Math.round(c[4]), absd_rate:absdRate(p.absdRes, p.propsAfter), binding_constraint:why };
    if (!best || r.max_price > best.max_price) best = r;
  }
  return best;
}
function stampDuty(price, residency, count) {
  const b = bsd(price), rate = absdRate(residency, count);
  return { price:Math.round(price), residency, property_count_after_purchase:count, bsd:Math.round(b), absd_rate:rate, absd:Math.round(price * rate), total_stamp_duty:Math.round(b + price * rate), policy_as_of:R.POLICY_AS_OF };
}

/* ================= Eligibility & scoring (mirror of advisor.py) ================= */
function E() { return { status:"eligible", reasons:[], notes:[],
  block(r) { this.status = "not_eligible"; this.reasons.push(r); },
  cond(r) { if (this.status !== "not_eligible") this.status = "conditional"; this.reasons.push(r); } }; }
function mop(p, e) { const c = p.cp; if (c && (c.type === "HDB" || c.type === "EC") && c.years < R.MOP) e.cond(`Current ${c.type} has not met the ${R.MOP}-year MOP (~${(R.MOP - c.years).toFixed(1)} more years), so it can't be sold and private can't be bought until then.`); }
const CHECKS = {
  HDB_RESALE(p) { const e = E(), c = p.cp;
    if (!p.hasSC) { if (p.residency === "PR" && p.co === "PR" && p.isFamily) e.cond("PR households need both owners to have held PR for at least 3 years; no CPF housing grants for PR-PR households."); else e.block("HDB flats need at least one Singapore Citizen buyer (or a PR-PR family). Foreigners and single PRs cannot buy HDB."); }
    if (p.hasSC && !p.isFamily && p.age < R.SINGLE_MIN_AGE) e.block(`Singles must be at least ${R.SINGLE_MIN_AGE} to buy an HDB resale flat.`);
    if (p.purpose === "investment") e.block("HDB flats must be owner-occupied, so they don't work as an investment purchase.");
    if (p.keeps) e.block("Can't keep the current property and buy an HDB flat. HDB buyers may own only one HDB and no private property.");
    if (p.ownsPrivate && !p.sells) e.block("Owners of private property must sell it before buying HDB.");
    if (c && (c.type === "PRIVATE" || c.type === "LANDED") && c.plan === "sell") e.cond(`After selling private property there is a ${R.PRIV_TO_HDB_M}-month wait before buying a resale HDB (seniors 55+ buying a 4-room or smaller are exempt).`);
    if (p.sinceDisposed != null && p.sinceDisposed * 12 < R.PRIV_TO_HDB_M) e.cond(`Private property sold less than ${R.PRIV_TO_HDB_M} months ago, so the wait-out applies.`);
    if (c && (c.type === "HDB" || c.type === "EC")) mop(p, e);
    if (p.hasSC && p.income <= R.HDB_INC_CEIL) e.notes.push("May qualify for CPF Housing Grants. Check the HDB Flat Eligibility letter.");
    return e; },
  EC_NEW_LAUNCH(p) { const e = E(), c = p.cp;
    if (!p.hasSC) e.block("New ECs need at least one Singapore Citizen buyer.");
    else if (!p.isFamily) e.block("Singles can't buy new-launch ECs (only resale ECs after 10 years).");
    else if (p.buyers.includes("FOREIGNER")) e.block("New EC co-buyers must be Singapore Citizens or PRs.");
    if (p.income > R.EC_CEIL) e.block(`Household income $${fmt(p.income)} is above the EC ceiling of $${fmt(R.EC_CEIL)}/month.`);
    if (p.purpose === "investment") e.block("ECs have a 5-year MOP with owner-occupation, so they don't work as an investment purchase.");
    if (p.ownsPrivate) e.block(`Buyers can't own private property, or have sold one in the last ${R.PRIV_TO_EC_M} months, to buy a new EC.`);
    else if (p.sinceDisposed != null && p.sinceDisposed * 12 < R.PRIV_TO_EC_M) e.block(`Private property sold less than ${R.PRIV_TO_EC_M} months ago.`);
    if (c && (c.type === "HDB" || c.type === "EC")) { mop(p, e);
      e.cond(`Must sell the current ${c.type} within 6 months of collecting the EC keys. ABSD is paid upfront and refunded on sale (married SC couples).`);
      e.notes.push("Can keep living in the current flat during the ~3-4 years of EC construction."); }
    if (p.hasSC && p.income <= 12000) e.notes.push("Income at or below $12,000 may qualify for the CPF Housing Grant for ECs.");
    return e; },
  PRIVATE_RESALE(p) { const e = E(); priv(p, e); return e; },
  PRIVATE_NEW_LAUNCH(p) { const e = E(); priv(p, e);
    e.notes.push("Progressive payments: the loan is drawn in stages during construction (~3-4 years to TOP).");
    if (p.sells && p.household === "married_couple" && p.hasSC) e.notes.push("Married SC couples can buy first and get second-property ABSD back if they sell the current home within 6 months of TOP.");
    return e; },
  LANDED(p) { const e = E(), c = p.cp;
    if (p.buyers.includes("FOREIGNER")) e.block("Foreigners can't buy landed homes on the mainland (Sentosa Cove only, with SLA approval).");
    else if (p.buyers.includes("PR") && !p.hasSC) e.cond("PRs need approval from SLA's Land Dealings Approval Unit to buy landed, usually one home for own stay under strict criteria.");
    if (c && (c.type === "HDB" || c.type === "EC")) mop(p, e);
    return e; },
};
function priv(p, e) { const c = p.cp;
  if (c && (c.type === "HDB" || c.type === "EC")) mop(p, e);
  if (p.absdRes === "FOREIGNER") e.notes.push("Foreigners pay 60% ABSD (US, Swiss, Norwegian, Icelandic and Liechtenstein nationals may get SC treatment under FTAs; verify with IRAS).");
  if (p.keeps && p.propsAfter >= 2) e.notes.push("Buying while keeping the current home means second-property ABSD and a lower loan limit.");
}
function score(p, seg, e, status, aff) {
  if (e.status === "not_eligible") return [0, ["Not eligible"]];
  let s = 50; const why = [];
  s += { comfortable:30, stretch:5, out_of_reach:-40 }[status]; why.push(`Affordability: ${status.replace(/_/g, " ")}`);
  if (e.status === "conditional") { s -= 10; why.push("Has conditions to meet first"); }
  if (aff.absd_rate > 0) { s -= Math.trunc(aff.absd_rate * 60); why.push(`ABSD of ${Math.round(aff.absd_rate * 100)}% adds a big upfront cost`); }
  const nl = seg === "EC_NEW_LAUNCH" || seg === "PRIVATE_NEW_LAUNCH";
  if (nl && p.timeline === "immediate") { s -= 15; why.push("New launches take ~3-4 years to complete"); }
  if (!nl && p.timeline === "immediate") { s += 5; why.push("Ready to move in"); }
  if (nl && p.timeline === "flexible") { s += 5; why.push("Progressive payments ease cash flow during construction"); }
  if (seg === "EC_NEW_LAUNCH") { s += 10; why.push("Condo living below private prices; becomes private after 10 years"); }
  if (seg === "HDB_RESALE" && p.income <= R.HDB_INC_CEIL && p.hasSC) { s += 5; why.push("Grants or an HDB loan may apply"); }
  if (p.purpose === "investment" && (seg === "PRIVATE_RESALE" || seg === "PRIVATE_NEW_LAUNCH")) { s += 10; why.push("Can be rented out with no occupancy rules"); }
  if (seg === "LANDED" && status === "comfortable") { s += 5; why.push("Scarce land supply tends to hold value"); }
  return [Math.max(0, Math.min(100, s)), why];
}
function analyse(input) {
  const p = makeProfile(input), fu = funds(p), out = [];
  for (const seg of Object.keys(CHECKS)) {
    const e = CHECKS[seg](p), band = R.BANDS[seg], aff = maxPrice(p, seg, fu);
    const status = aff.max_price >= band.typical ? "comfortable" : aff.max_price >= band.entry ? "stretch" : "out_of_reach";
    const [sc, why] = score(p, seg, e, status, aff);
    const target = Math.min(aff.max_price, band.typical), loanT = Math.min(target * aff.ltv, aff.max_loan_by_income);
    const ok = e.status !== "not_eligible";
    out.push({ segment:seg, label:LABELS[seg], eligibility:e.status, eligibility_reasons:e.reasons, notes:e.notes, price_band:band,
      max_affordable_price:aff, affordability: ok ? status : "n/a",
      illustrative_purchase: ok && status !== "out_of_reach" ? { price:Math.round(target), loan:Math.round(loanT), monthly_instalment:Math.round(instalment(loanT, R.MARKET_RATE, aff.tenure_years)), assumed_rate:R.MARKET_RATE } : null,
      suitability_score:sc, score_factors:why });
  }
  out.sort((a, b) => b.suitability_score - a.suitability_score);
  const viable = out.filter(r => r.eligibility !== "not_eligible" && r.affordability !== "out_of_reach");
  const r = v => Math.round(v);
  return { policy_as_of:R.POLICY_AS_OF,
    client_summary:{ buyers:p.buyers, household_type:p.household, absd_treated_as:p.absdRes, property_count_after_purchase:p.propsAfter,
      housing_loans_after_purchase:p.loansAfter, monthly_income:p.income,
      funds_available:{ cpf:r(fu.cpf), cash:r(fu.cash), sale_cash_proceeds:r(fu.sale_cash_proceeds), cpf_refund_from_sale:r(fu.cpf_refund_from_sale) } },
    top_recommendation: viable.length ? viable[0].label : null, ranked_options:out,
    disclaimer:"Indicative analysis using simplified rules and assumed prices. Confirm eligibility with HDB, stamp duties with IRAS, and loan amounts with a bank In-Principle Approval." };
}
