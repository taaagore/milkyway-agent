import unittest
import os
import json
from unittest.mock import patch, MagicMock
from PIL import Image

from app import app, vision_screen, risk_reasoner, route_decision


class MilkywayAgentTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Create a tiny real image file so vision_screen() can actually
        # open it (Image.open needs a real file, even though its content
        # doesn't matter since the Gemini call itself is mocked below).
        cls.test_image_path = "test_dummy_image.jpg"
        img = Image.new('RGB', (10, 10), color='white')
        img.save(cls.test_image_path)

    @classmethod
    def tearDownClass(cls):
        try:
            if os.path.exists(cls.test_image_path):
                os.remove(cls.test_image_path)
        except PermissionError:
            pass  # Windows file lock quirk, harmless

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def _mock_gemini_response(self, reading, confidence):
        """Builds a fake Gemini response with the given JSON text,
        so vision_screen() parses it exactly like a real response."""
        mock_response = MagicMock()
        mock_response.text = json.dumps({"reading": reading, "confidence": confidence})
        return mock_response

    # --- vision_screen tests -------------------------------------------

    @patch('app._gemini_client.models.generate_content')
    def test_vision_screen_success(self, mock_generate):
        mock_generate.return_value = self._mock_gemini_response(29.5, 0.95)
        reading, conf = vision_screen(self.test_image_path)
        self.assertEqual(reading, 29.5)
        self.assertEqual(conf, 0.95)

    @patch('app._gemini_client.models.generate_content')
    def test_vision_screen_api_failure(self, mock_generate):
        mock_generate.side_effect = Exception("Simulated API failure")
        reading, conf = vision_screen(self.test_image_path)
        self.assertEqual(reading, 0.0)
        self.assertEqual(conf, 0.0)

    def test_vision_screen_missing_file(self):
        reading, conf = vision_screen("this_file_does_not_exist.jpg")
        self.assertEqual(reading, 0.0)
        self.assertEqual(conf, 0.0)

    # --- risk_reasoner tests (unchanged, already passing) ---------------

    def test_risk_reasoner(self):
        verdict, explanation, conf = risk_reasoner(29.0, 'cow')
        self.assertEqual(verdict, 'SAFE')
        self.assertGreaterEqual(conf, 0.80)

        verdict, explanation, conf = risk_reasoner(24.0, 'cow')
        self.assertEqual(verdict, 'RISKY')
        self.assertGreaterEqual(conf, 0.80)

        verdict, explanation, conf = risk_reasoner(31.5, 'buffalo')
        self.assertEqual(verdict, 'SAFE')
        self.assertGreaterEqual(conf, 0.80)

        verdict, explanation, conf = risk_reasoner(29.5, 'buffalo')
        self.assertEqual(verdict, 'RISKY')
        self.assertGreaterEqual(conf, 0.80)

        verdict, explanation, conf = risk_reasoner(5.0, 'cow')
        self.assertEqual(verdict, 'INVALID')

    # --- route_decision tests (unchanged, already passing) --------------

    def test_route_decision(self):
        escalate, reason = route_decision(0.95, 0.95, 0.80)
        self.assertFalse(escalate)

        escalate, reason = route_decision(0.50, 0.95, 0.80)
        self.assertTrue(escalate)
        self.assertIn("Vision screen confidence", reason)

        escalate, reason = route_decision(0.95, 0.60, 0.80)
        self.assertTrue(escalate)
        self.assertIn("Risk reasoner confidence", reason)

        escalate, reason = route_decision(0.50, 0.50, 0.80)
        self.assertTrue(escalate)
        self.assertIn("Vision screen confidence", reason)
        self.assertIn("Risk reasoner confidence", reason)

    # --- API endpoint tests ----------------------------------------------

    def test_reference_api_get(self):
        res_get = self.app.get('/api/reference')
        self.assertEqual(res_get.status_code, 200)
        data_get = json.loads(res_get.data)
        self.assertIn('content', data_get)
        self.assertIn('parsed_standard', data_get)
        self.assertEqual(data_get['parsed_standard'], 28.0)

    def test_reference_api_post_rejected(self):
        # POST should be rejected now that write access was removed
        # for security reasons.
        res_post = self.app.post('/api/reference', json={'content': 'test'})
        self.assertEqual(res_post.status_code, 405)

    @patch('app._gemini_client.models.generate_content')
    def test_analyze_safe_case(self, mock_generate):
        mock_generate.return_value = self._mock_gemini_response(29.5, 0.95)
        with open(self.test_image_path, 'rb') as img_file:
            data = {
                'milk_type': 'cow',
                'threshold': '0.80',
                'photo': (img_file, 'test.jpg'),
            }
            res = self.app.post('/api/analyze', data=data, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 200)
        result = json.loads(res.data)
        self.assertEqual(result['vision_screen']['reading'], 29.5)
        self.assertFalse(result['routing']['escalate'])
        self.assertEqual(result['routing']['final_status'], 'SAFE')

    @patch('app._gemini_client.models.generate_content')
    def test_analyze_escalation_case(self, mock_generate):
        mock_generate.return_value = self._mock_gemini_response(28.5, 0.45)
        with open(self.test_image_path, 'rb') as img_file:
            data = {
                'milk_type': 'cow',
                'threshold': '0.80',
                'photo': (img_file, 'test.jpg'),
            }
            res = self.app.post('/api/analyze', data=data, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 200)
        result = json.loads(res.data)
        self.assertTrue(result['routing']['escalate'])
        self.assertEqual(result['routing']['final_status'], 'ESCALATED TO HUMAN REVIEW')

    def test_analyze_missing_milk_type(self):
        with open(self.test_image_path, 'rb') as img_file:
            data = {'photo': (img_file, 'test.jpg')}
            res = self.app.post('/api/analyze', data=data, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 400)

    def test_analyze_invalid_milk_type(self):
        with open(self.test_image_path, 'rb') as img_file:
            data = {'milk_type': 'sheep', 'photo': (img_file, 'test.jpg')}
            res = self.app.post('/api/analyze', data=data, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 400)

    def test_analyze_missing_photo(self):
        data = {'milk_type': 'cow'}
        res = self.app.post('/api/analyze', data=data, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 400)


if __name__ == '__main__':
    unittest.main()