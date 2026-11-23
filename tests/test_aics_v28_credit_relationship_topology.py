"""V28 original-source credit topology gates: never infer a current debt matrix."""
import copy
import json
import unittest

from scripts.aics_v28_credit_relationship_topology import (
    build, read, WARD, KVANDAL, NEBIUS, REGISTRY, OBSERVED, nc_audit
)
from scripts.aics_spv_funding_transmission_bridge import (
    build as build_spv, CORE, CLOUD, NSCALE, DFS
)


class LegalCreditTopologyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw=REGISTRY.read_bytes()
        cls.nc=nc_audit(json.loads(raw),read(OBSERVED),raw)
        cls.ward=read(WARD)
        cls.kvandal=read(KVANDAL)
        cls.nebius=read(NEBIUS)
        cls.spv_inputs=[read(x) for x in (CORE,CLOUD,NSCALE,DFS)]

    def calculate(self, *, as_of="2026-11-21", ward=None, nc=None,
                  kvandal=None, nebius=None):
        bridge=build_spv(*self.spv_inputs,as_of=as_of)
        return build(
            bridge=bridge,
            ward=self.ward if ward is None else ward,
            nc_contract=self.nc if nc is None else nc,
            kvandal=self.kvandal if kvandal is None else kvandal,
            nebius=self.nebius if nebius is None else nebius,
            as_of=as_of)

    def test_actual_legal_topology_nonadditive_and_not_predictive(self):
        x=self.calculate()
        e={z["id"]:z for z in x["relationships"]}
        self.assertEqual(len(e),9)
        self.assertEqual(x["historical_coreweave_two_facility_debt_count"],2)
        self.assertEqual(x["named_financing_provider_relationship_count"],2)
        self.assertEqual(x["named_guarantor_legal_links"],2)
        self.assertEqual(e["MACQUARIE_HISTORY"]["from"],"Macquarie Bank Limited")
        self.assertEqual(e["MACQUARIE_HISTORY"]["amount_usd_m"],105)
        self.assertIn("not_current_outstanding",e["MACQUARIE_HISTORY"]["amount_semantics"])
        self.assertEqual(e["DELL_GROUP_RENT"]["from"],"Dell Financial Services L.L.C.")
        self.assertEqual(e["DELL_GROUP_RENT"]["amount_usd_m"],2540)
        self.assertTrue(e["DELL_GROUP_RENT"]["borrower_group_not_per_borrower_split"])
        self.assertEqual(e["WARD_LIMIT"]["amount_usd_m"],1850)
        self.assertEqual(e["NC_LIMIT"]["amount_usd_m"],1200)
        self.assertEqual(e["KVANDAL_TERM_DRAW"]["amount_usd_m"],88.1)
        self.assertEqual(e["KVANDAL_VAT_DRAW"]["amount_usd_m"],19.1)
        self.assertEqual(e["NEBIUS_6K_CAPACITY"]["amount_usd_m"],3500)
        self.assertEqual(x["historical_kvandal_period_draws_total_usd_m_not_outstanding"],"107.2")
        self.assertEqual({z["guarantor"] for z in x["guarantor_relationships"]},
                         {"Nscale Ward County, LLC","Nscale Services US Inc."})
        self.assertTrue(all(z["combined_effective_exposure_usd_m"] is None
                            and not z["current_credit_exposure_verified"] for z in e.values()))
        self.assertEqual(x["current_named_lender_to_borrower_dollar_exposure_edges"],0)
        self.assertIsNone(x["current_lender_borrower_dollar_exposure_matrix"])
        self.assertIsNone(x["same_date_present_value_of_all_relationships_usd_m"])
        self.assertIsNone(x["historical_2008_similarity_pct"])
        self.assertIsNone(x["crisis_forecast_probability"])
        self.assertIsNone(x["index_aics"])
        self.assertFalse(x["production_weights_changed"])

    def test_date_gates_do_not_move_2026_sources_earlier(self):
        for cutoff,edges,guarantees,providers in [
            ("2026-08-25",0,0,0),
            ("2026-08-26",2,0,0),
            ("2026-10-01",2,0,0),
            ("2026-10-02",8,2,2),
            ("2026-11-04",8,2,2),
            ("2026-11-05",9,2,2),
        ]:
            with self.subTest(cutoff=cutoff):
                x=self.calculate(as_of=cutoff)
                self.assertEqual(len(x["relationships"]),edges)
                self.assertEqual(x["named_guarantor_legal_links"],guarantees)
                self.assertEqual(x["named_financing_provider_relationship_count"],providers)

    def test_forged_ward_or_nc_funded_debt_blocks(self):
        for key,value in [
            ("facility_commitment_ceiling_usd",2000000000),
            ("drawn_principal_for_either_facility_usd",1850000000),
            ("parent_guarantee_amount_usd",630000000),
            ("sec_available_at","2026-09-18"),
        ]:
            bad=copy.deepcopy(self.ward)
            bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                self.calculate(ward=bad)
        nc=copy.deepcopy(self.nc)
        nc["drawn_principal_usd"]=1200000000
        with self.assertRaises(ValueError):
            self.calculate(nc=nc)

    def test_forged_kvandal_balances_or_nubius_debt_blocks(self):
        for key,value in [("closing_balance",107.2),("draws_in_period_total",110)]:
            bad=copy.deepcopy(self.kvandal)
            bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                self.calculate(kvandal=bad)
        for field,value in [
            ("amount_currently_drawn_usd",3500000000),
            ("aggregate_principal_capacity_usd",7000000000),
        ]:
            bad=copy.deepcopy(self.nebius)
            bad["terms"][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                self.calculate(nebius=bad)

    def test_bad_pub_date_or_fake_spv_identification_blocks(self):
        bad=copy.deepcopy(self.nebius)
        bad["available_at"]="2026-10-22"
        with self.assertRaises(ValueError):
            self.calculate(nebius=bad)
        bad=copy.deepcopy(self.nebius)
        bad["spv_legal_structure_proven"]=True
        with self.assertRaises(ValueError):
            self.calculate(nebius=bad)


if __name__=="__main__":
    unittest.main()
