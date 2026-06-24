import unittest
import os
import json
from app import app, vision_screen, risk_reasoner, route_decision

class MilkywayAgentTests(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_vision_screen(self):
        # Mock responses based on file name characteristics
        reading, conf = vision_screen("pure_milk_sample.jpg")
        self.assertEqual(reading, 29.5)
        self.assertEqual(conf, 0.96)
        
        reading, conf = vision_screen("water_diluted.jpg")
        self.assertEqual(reading, 22.0)
        self.assertEqual(conf, 0.94)

        reading, conf = vision_screen("blurry_image.jpg")
        self.assertEqual(reading, 28.5)
        self.assertEqual(conf, 0.45)

        reading, conf = vision_screen("extreme_invalid.jpg")
        self.assertEqual(reading, 12.0)
        self.assertEqual(conf, 0.98)

    def test_risk_reasoner(self):
        # Safe reading for Cow (MIN 28.0)
        verdict, explanation, conf = risk_reasoner(29.0, 'cow')
        self.assertEqual(verdict, 'SAFE')
        self.assertGreaterEqual(conf, 0.80)

        # Risky reading for Cow (adulterated)
        verdict, explanation, conf = risk_reasoner(24.0, 'cow')
        self.assertEqual(verdict, 'RISKY')
        self.assertGreaterEqual(conf, 0.80)

        # Safe reading for Buffalo (MIN 30.0)
        verdict, explanation, conf = risk_reasoner(31.5, 'buffalo')
        self.assertEqual(verdict, 'SAFE')
        self.assertGreaterEqual(conf, 0.80)

        # Risky reading for Buffalo (adulterated)
        verdict, explanation, conf = risk_reasoner(29.5, 'buffalo')
        self.assertEqual(verdict, 'RISKY')
        self.assertGreaterEqual(conf, 0.80)

        # Invalid reading
        verdict, explanation, conf = risk_reasoner(5.0, 'cow')
        self.assertEqual(verdict, 'INVALID')

    def test_route_decision(self):
        # Case 1: All confidences above threshold
        escalate, reason = route_decision(0.95, 0.95, 0.70)
        self.assertFalse(escalate)

        # Case 2: Vision confidence below threshold
        escalate, reason = route_decision(0.50, 0.95, 0.70)
        self.assertTrue(escalate)
        self.assertIn("Vision screen confidence", reason)

        # Case 3: Risk confidence below threshold
        escalate, reason = route_decision(0.95, 0.60, 0.70)
        self.assertTrue(escalate)
        self.assertIn("Risk reasoner confidence", reason)

        # Case 4: Both below threshold
        escalate, reason = route_decision(0.50, 0.50, 0.70)
        self.assertTrue(escalate)
        self.assertIn("Vision screen confidence", reason)
        self.assertIn("Risk reasoner confidence", reason)

    def test_api_endpoints(self):
        # 1. Test Reference API (GET)
        res_get = self.app.get('/api/reference')
        self.assertEqual(res_get.status_code, 200)
        data_get = json.loads(res_get.data)
        self.assertIn('content', data_get)
        self.assertIn('parsed_standard', data_get)
        self.assertEqual(data_get['parsed_standard'], 28.0)

        # 2. Test Analyze API (POST) - Safe Case (Cow)
        payload = {
            'photo_path': 'pure_milk_sample.jpg',
            'threshold': 0.70,
            'milk_type': 'cow'
        }
        res_post = self.app.post('/api/analyze', json=payload)
        self.assertEqual(res_post.status_code, 200)
        data_post = json.loads(res_post.data)
        self.assertEqual(data_post['vision_screen']['reading'], 29.5)
        self.assertFalse(data_post['routing']['escalate'])
        self.assertEqual(data_post['routing']['final_status'], 'SAFE')

        # 3. Test Analyze API (POST) - Safe Case (Buffalo)
        payload_buffalo = {
            'photo_path': 'pure_buffalo_milk.jpg',
            'threshold': 0.70,
            'milk_type': 'buffalo'
        }
        res_post_buffalo = self.app.post('/api/analyze', json=payload_buffalo)
        self.assertEqual(res_post_buffalo.status_code, 200)
        data_buffalo = json.loads(res_post_buffalo.data)
        self.assertEqual(data_buffalo['vision_screen']['reading'], 31.5)
        self.assertFalse(data_buffalo['routing']['escalate'])
        self.assertEqual(data_buffalo['routing']['final_status'], 'SAFE')

        # 4. Test Analyze API (POST) - Escalation due to low confidence
        payload_escalate = {
            'photo_path': 'blurry_lactometer.jpg',
            'threshold': 0.70,
            'milk_type': 'cow'
        }
        res_post_escalate = self.app.post('/api/analyze', json=payload_escalate)
        self.assertEqual(res_post_escalate.status_code, 200)
        data_escalate = json.loads(res_post_escalate.data)
        self.assertTrue(data_escalate['routing']['escalate'])
        self.assertEqual(data_escalate['routing']['final_status'], 'ESCALATED TO HUMAN REVIEW')

        # 5. Test Analyze API (POST) - Missing milk_type validation
        payload_missing = {
            'photo_path': 'pure_milk_sample.jpg',
            'threshold': 0.70
        }
        res_post_missing = self.app.post('/api/analyze', json=payload_missing)
        self.assertEqual(res_post_missing.status_code, 400)

        # 6. Test Analyze API (POST) - Invalid milk_type validation
        payload_invalid = {
            'photo_path': 'pure_milk_sample.jpg',
            'threshold': 0.70,
            'milk_type': 'sheep'
        }
        res_post_invalid = self.app.post('/api/analyze', json=payload_invalid)
        self.assertEqual(res_post_invalid.status_code, 400)

if __name__ == '__main__':
    unittest.main()
