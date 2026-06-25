"""
test_engines.py — Unit Tests for Critical Path Engines
AI TO AI HOLDING — Customs Intelligence Division
"""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestTaxEngine(unittest.TestCase):
    def test_import(self):
        import tax_engine_bundled as te
        self.assertTrue(hasattr(te, 'lookup_tax'))
    def test_lookup(self):
        import tax_engine_bundled as te
        result = te.lookup_tax("8471")
        self.assertIsNotNone(result)

class TestHalalEngine(unittest.TestCase):
    def test_import(self):
        import halal_engine
        self.assertTrue(hasattr(halal_engine, 'check'))
    def test_check(self):
        import halal_engine as he
        result = he.check("0201")
        self.assertIn("halal_required", result)
        self.assertIn("hs_chapter", result)

class TestOGAEngine(unittest.TestCase):
    def test_import(self):
        import oga_engine as oe
        self.assertTrue(hasattr(oe, 'check'))
        self.assertTrue(hasattr(oe, 'check_batch'))
    def test_check_hs(self):
        import oga_engine as oe
        result = oe.check("2204")
        self.assertIn("is_restricted", result)
        self.assertTrue(result["is_restricted"])
    def test_agencies_count(self):
        import oga_engine as oe
        self.assertGreaterEqual(len(oe.get_all_agencies()), 36)
    def test_batch_check(self):
        import oga_engine as oe
        self.assertEqual(len(oe.check_batch(["8517","2204","3004"])), 3)
    def test_documents_checklist(self):
        import oga_engine as oe
        r = oe.get_documents_checklist("2204")
        self.assertIn("standard_documents", r)
    def test_restricted_chapters(self):
        import oga_engine as oe
        self.assertGreater(len(oe.get_restricted_chapters_summary()), 0)

class TestLandedCostEngine(unittest.TestCase):
    def test_import(self):
        import landed_cost_engine as lce
        self.assertTrue(hasattr(lce, 'calculate_landed_cost'))
    def test_calculate(self):
        import landed_cost_engine as lce
        result = lce.calculate_landed_cost(product_value=10000, hs_code="8471", origin_country="CN", incoterm="FOB", weight_kg=500)
        self.assertIsNotNone(result)
        self.assertGreater(result.to_dict()["totals"]["total_landed_cost_usd"], 0)
    def test_all_incoterms(self):
        import landed_cost_engine as lce
        self.assertGreaterEqual(len(lce.get_all_incoterms()), 11)
    def test_compare_incoterms(self):
        import landed_cost_engine as lce
        result = lce.compare_incoterms(product_values={"FOB": 10000}, hs_code="8471", origin_country="CN")
        self.assertGreater(len(result), 0)

class TestPriceBenchmarkEngine(unittest.TestCase):
    def test_import(self):
        import price_benchmark_engine as pbe
        self.assertTrue(hasattr(pbe, 'assess_valuation_risk'))
    def test_assess_risk(self):
        import price_benchmark_engine as pbe
        result = pbe.get_reference_benchmarks()
        self.assertIsNotNone(result)
    def test_reference_benchmarks(self):
        import price_benchmark_engine as pbe
        self.assertGreater(len(pbe.get_reference_benchmarks()), 0)

class TestFreightAuditorEngine(unittest.TestCase):
    def test_import(self):
        import freight_auditor_engine as fae
        self.assertTrue(hasattr(fae, 'audit_freight_bill'))
        self.assertTrue(hasattr(fae, 'get_market_rate_card'))
    def test_audit_bill(self):
        import freight_auditor_engine as fae
        charges = [fae.ChargeLineItem(charge_type="ocean_freight", description="Sea freight", amount_usd=3000)]
        result = fae.audit_freight_bill(charges=charges, shipment_mode="sea")
        self.assertIn("total_charged_usd", result.to_dict())
    def test_market_rate_card(self):
        import freight_auditor_engine as fae
        self.assertIsInstance(fae.get_market_rate_card(), list)

class TestWhatIfEngine(unittest.TestCase):
    def test_import(self):
        import whatif_optimizer_engine as wie
        self.assertTrue(hasattr(wie, 'simulate_scenarios'))
        self.assertTrue(hasattr(wie, 'duty_engineering_analysis'))
    def test_simulate(self):
        import whatif_optimizer_engine as wie
        result = wie.simulate_scenarios(product_value=10000, hs_code="8471", origin_country="CN", mfn_duty_rate=0.05)
        self.assertIn("options", result.to_dict())
    def test_duty_engineering(self):
        import whatif_optimizer_engine as wie
        result = wie.duty_engineering_analysis("8471", "CN", product_value=10000, mfn_rate=0.05)
        self.assertIsInstance(result, dict)

class TestCustomsAuditEngine(unittest.TestCase):
    def test_import(self):
        import customs_audit_engine as cae
        self.assertTrue(hasattr(cae, 'RISK_WEIGHTS'))
    def test_risk_weights_sum(self):
        import customs_audit_engine as cae
        self.assertEqual(sum(cae.RISK_WEIGHTS.values()), 100)
    def test_score_to_grade(self):
        import customs_audit_engine as cae
        self.assertEqual(cae._score_to_grade(15)[0], "A")
        self.assertEqual(cae._score_to_grade(30)[0], "B")
        self.assertEqual(cae._score_to_grade(50)[0], "C")
        self.assertEqual(cae._score_to_grade(70)[0], "D")
        self.assertEqual(cae._score_to_grade(90)[0], "F")
    def test_high_risk_chapters(self):
        import customs_audit_engine as cae
        self.assertIn("71", cae.HIGH_RISK_CHAPTERS)
        self.assertIn("85", cae.HIGH_RISK_CHAPTERS)

class TestCBAMCarbonEngine(unittest.TestCase):
    def test_import(self):
        import cbam_carbon_engine as cce
        self.assertTrue(hasattr(cce, 'calculate_carbon_footprint'))
    def test_cbam_sectors(self):
        import cbam_carbon_engine as cce
        self.assertEqual(len(cce.get_cbam_sectors()), 6)
    def test_cbam_steel(self):
        import cbam_carbon_engine as cce
        r = cce.check_cbam_applicability("7208")
        self.assertTrue(r["cbam_applicable"])
        self.assertEqual(r["sector"], "iron_steel")
    def test_cbam_non_applicable(self):
        import cbam_carbon_engine as cce
        self.assertFalse(cce.check_cbam_applicability("8471")["cbam_applicable"])
    def test_calculate_footprint(self):
        import cbam_carbon_engine as cce
        fp = cce.calculate_carbon_footprint(hs_code="7208", weight_kg=10000, origin_country="CN")
        d = fp.to_dict()
        self.assertGreater(d["total_emissions_kg_co2e"], 0)
        self.assertTrue(d["cbam_applicable"])
        self.assertGreater(d["estimated_cbam_cost_eur"], 0)
    def test_grid_factors(self):
        import cbam_carbon_engine as cce
        self.assertEqual(cce.get_grid_factors()["factors"]["TH"], 475)
    def test_emission_factor(self):
        import cbam_carbon_engine as cce
        ef = cce.get_emission_factor("7201")
        self.assertTrue(ef["found"])
        self.assertEqual(ef["factor"], 1987)
    def test_carbon_report(self):
        import cbam_carbon_engine as cce
        items = [{"hs_code":"7208","weight_kg":5000,"origin_country":"CN","description":"Steel"},
                 {"hs_code":"7601","weight_kg":2000,"origin_country":"CN","description":"Aluminium"}]
        r = cce.generate_carbon_report(items)
        d = r.to_dict()
        self.assertEqual(d["summary"]["total_items"], 2)
        self.assertEqual(d["summary"]["cbam_items_count"], 2)

class TestASEANExpansionEngine(unittest.TestCase):
    def test_countries_count(self):
        import asean_expansion_engine as aee
        self.assertEqual(len(aee.get_all_countries()), 6)
    def test_compare_duties(self):
        import asean_expansion_engine as aee
        d = aee.compare_duties("8703").to_dict()
        self.assertEqual(len(d["comparisons"]), 6)
        self.assertEqual(d["cheapest"]["country"], "SG")
    def test_check_compliance(self):
        import asean_expansion_engine as aee
        d = aee.check_compliance("8517","TH").to_dict()
        self.assertEqual(d["coverage_status"], "LIVE")
        self.assertIn("ATIGA", d["ftas_available"])
    def test_multi_country(self):
        import asean_expansion_engine as aee
        self.assertEqual(len(aee.multi_country_check("6203",["TH","VN","SG"])), 3)
    def test_expansion_status(self):
        import asean_expansion_engine as aee
        s = aee.get_expansion_status()
        self.assertIn("TH", s["live"])
        self.assertEqual(len(s["beta"]), 3)
        self.assertEqual(len(s["planned"]), 2)
    def test_unsupported_country(self):
        import asean_expansion_engine as aee
        self.assertEqual(aee.check_compliance("8517","XX").to_dict()["coverage_status"], "NOT_SUPPORTED")

class TestValuationEngine(unittest.TestCase):
    def test_full_valuation(self):
        import valuation_engine as ve
        d = ve.calculate_full_valuation().to_dict()
        self.assertEqual(len(d["dimensions"]), 12)
        self.assertGreater(d["summary"]["weighted_fair_value_thb"], 15_000_000)
    def test_base_value_floor(self):
        import valuation_engine as ve
        self.assertGreaterEqual(ve.calculate_full_valuation(base_value_thb=15_000_000).weighted_fair_value_thb, 15_000_000)
    def test_litigation_value(self):
        import valuation_engine as ve
        r = ve.calculate_litigation_value()
        self.assertIn("civil_damages", r)
        self.assertGreater(r["civil_damages"]["total_claim_thb"], 0)
    def test_feature_portfolio(self):
        import valuation_engine as ve
        r = ve.get_feature_portfolio()
        self.assertEqual(r["total_modules"], 20)
    def test_growth_projection(self):
        import valuation_engine as ve
        r = ve.project_growth(current_users=50, months=60)
        self.assertEqual(len(r["projections"]), 5)
        self.assertGreater(r["projections"][-1]["projected_valuation_thb"], r["projections"][0]["projected_valuation_thb"])
    def test_feature_modules_completeness(self):
        import valuation_engine as ve
        for key, mod in ve.FEATURE_MODULES.items():
            self.assertIn("name_th", mod)
            self.assertGreater(mod["market_value_thb"], 0)

class TestPricingEngine(unittest.TestCase):
    def test_import(self):
        import pricing_engine as pe
        self.assertTrue(hasattr(pe, 'get_all_tiers'))
    def test_tiers(self):
        import pricing_engine as pe
        self.assertGreaterEqual(len(pe.get_all_tiers()), 6)

class TestMembershipEngine(unittest.TestCase):
    def test_import(self):
        import membership_engine as me
        self.assertTrue(hasattr(me, 'calculate_tier'))
    def test_tier_thresholds(self):
        import membership_engine as me
        self.assertTrue(hasattr(me, 'TIER_THRESHOLDS'))
        self.assertGreaterEqual(len(me.TIER_THRESHOLDS), 5)

class TestKillSwitchEngine(unittest.TestCase):
    def test_import(self):
        import kill_switch_engine as kse
        self.assertTrue(hasattr(kse, 'get_state'))
    def test_default_state(self):
        import kill_switch_engine as kse
        self.assertIn("state", kse.get_state())

if __name__ == "__main__":
    unittest.main(verbosity=2)
