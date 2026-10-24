from interviewos.match import finance_profile, passes_domain
from interviewos.models import JobHit

PROFILE = (
    "Product manager with 4+ years taking enterprise AI products from strategy through deployment. "
    "Founder's office work on product and GTM."
)


def _job(title: str, company: str, description: str = "") -> JobHit:
    return JobHit(title=title, company_name=company, description_excerpt=description)


def test_traced_bank_roles_fail_for_an_ai_gtm_profile():
    rejected = [
        _job("Product Manager- UPI & Payments Product", "Canara Bank", "Own the UPI payments roadmap."),
        _job("Product Manager - Cash Management Services", "CSB Bank", "Cash management for corporate clients."),
        _job("Wholesale Credit Risk Associate - Product Strategy", "JPMorganChase", "Wholesale credit risk for the bank."),
        _job("Senior Product Manager - APAC", "Barclays", "Markets product for the bank."),
        _job("Credit Product Strategy - Vice President", "Citi", "Credit strategy for consumer banking."),
        _job("Product Manager/Product Owner , BFS Consulting", "Cognizant", "Banking and financial services consulting."),
    ]
    assert finance_profile(PROFILE) is False
    assert all(passes_domain(job, PROFILE) is False for job in rejected)


def test_ai_gtm_role_passes_and_a_credit_risk_profile_may_keep_a_bank():
    fit = _job(
        "Senior Technical Product Manager",
        "Optum",
        "Product marketing and AI content for an enterprise platform.",
    )
    assert passes_domain(fit, PROFILE) is True
    banker = "Underwriting and credit risk for retail banking clients."
    bank_job = _job("Product Strategy", "Canara Bank", "Retail banking product.")
    assert passes_domain(bank_job, banker) is True
