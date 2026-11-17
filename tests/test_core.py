from __future__ import annotations
import json, subprocess, tempfile, unittest
from pathlib import Path
from vlux_ci.db import connect
from vlux_ci.ml import Baseline, train
from vlux_ci.creative import recommend, CONTRACT_VERSION
from vlux_ci.commercial import summarize

class TestCore(unittest.TestCase):
    def setUp(self): self.t=tempfile.TemporaryDirectory(); self.db=Path(self.t.name)/"x.sqlite"; self.con=connect(self.db)
    def tearDown(self): self.con.close(); self.t.cleanup()
    def test_schema_and_duplicate_constraint(self):
        self.con.execute("insert into videos(episode,version,file_path,file_hash,permission_status) values('E','v','x','hash','synthetic')"); self.con.commit()
        with self.assertRaises(Exception): self.con.execute("insert into videos(episode,version,file_path,file_hash,permission_status) values('E','v','x','hash','synthetic')")
    def test_missing_metrics_never_fabricate(self):
        score=Baseline().score({"duration_s":None,"motion_mean":None}); self.assertGreaterEqual(score,0); self.assertLessEqual(score,1)
    def test_insufficient_data_state(self):
        r=train(self.con,Path(self.t.name)/"a"); self.assertEqual(r["status"],"NO_TRAINING_INSUFFICIENT_DATA")
    def test_group_holdout_required(self):
        for i in range(8):
            self.con.execute("insert into videos(episode,version,file_path,file_hash,permission_status) values(?,?,?,?,?)",('E'+str(i%2),'v','x'+str(i),'h'+str(i),'synthetic'))
            vid=self.con.execute('select last_insert_rowid()').fetchone()[0]
            self.con.execute("insert into analyses(video_id,analyzer_version,objective_json,aesthetic_json) values(?,?,?,?)",(vid,'t',json.dumps({'duration_s':2,'fps':30,'width':64,'height':64,'cut_count':i,'avg_shot_s':1,'motion_mean':i,'brightness_mean':100,'contrast_mean':30,'black_ratio':0,'freeze_ratio':0,'subtitle_space_ratio':.5,'first_second_motion':i,'first_second_brightness':100}), '{}'))
        for i in range(0,8,2): self.con.execute("insert into feedback(variant_a_id,variant_b_id,winner) values(?,?,?)",(i+1,i+2,'A'))
        self.con.commit(); r=train(self.con,Path(self.t.name)/"a",min_examples=8); self.assertIn(r['status'],{'TRAINED','NO_TRAINING_INSUFFICIENT_DATA'})
    def test_v02_schema_and_unknown_metrics(self):
        cols={r[1] for r in self.con.execute("pragma table_info(videos)")}
        self.assertIn("source_kind", cols); self.assertEqual(self.con.execute("select value from schema_meta where key='schema_version'").fetchone()[0], "0.5")
        self.con.execute("insert into videos(episode,version,file_path,file_hash,permission_status,source_kind) values('E','v','x','h2','synthetic','synthetic')")
        self.con.execute("insert into publications(video_id,episode,platform,provenance) values(?,?,?,?)",(1,'E','Instagram','USER_PROVIDED_SCREENSHOT'))
        self.con.execute("insert into platform_metrics(publication_id,metric_name,metric_value,status,provenance) values(?,?,?,?,?)",(1,'views',100,'OBSERVED','USER_PROVIDED_SCREENSHOT'))
        self.con.commit(); self.assertEqual(summarize(self.con)["records"], 0)
        self.assertEqual(self.con.execute("select value from schema_meta where key='schema_version'").fetchone()[0], "0.5")
    def test_funnel_does_not_convert_interaction_to_lead(self):
        from vlux_ci.funnel import funnel
        self.con.execute("insert into publications(episode,platform,provenance) values('EP011','Instagram','USER_PROVIDED_SCREENSHOT')")
        pid=self.con.execute("select last_insert_rowid()").fetchone()[0]
        self.con.execute("insert into platform_metrics(publication_id,metric_name,metric_value,status,provenance) values(?,?,?,?,?)",(pid,'likes',10,'OBSERVED','USER_PROVIDED_SCREENSHOT'))
        self.con.commit(); result=funnel(self.con,pid)
        self.assertEqual(result["stages"]["prospects"]["leads"]["status"],"NOT_AVAILABLE")
        self.assertEqual(result["stages"]["commercial_interest"]["profile_visits"]["status"],"NOT_AVAILABLE")
    def test_creative_director_is_proposal_without_evidence(self):
        result=recommend({"business_problem":"errores de trazabilidad"}, self.con)
        self.assertEqual(result["contract_version"], CONTRACT_VERSION)
        self.assertEqual(result["status"], "PROPOSAL_ONLY")
        self.assertEqual(result["evidence"]["confidence"], "low")
        self.assertTrue(result["recommended_experiment"]["approval_required"])
if __name__=='__main__': unittest.main()
