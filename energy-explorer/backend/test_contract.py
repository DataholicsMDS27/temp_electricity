import unittest
from fastapi.testclient import TestClient
from .main import app
from .schemas import Prediction


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.context = TestClient(app)
        self.client = self.context.__enter__()

    def tearDown(self):
        self.context.__exit__(None, None, None)

    def scenario(self, **changes):
        return {"temperature_c": 22, "day_type": "weekday", "hour": 14, **changes}

    def test_batch_coverage_and_determinism(self):
        metadata = self.client.get('/api/v1/metadata').json()
        first = self.client.post('/api/v1/predictions', json=self.scenario()).json()
        second = self.client.post('/api/v1/predictions', json=self.scenario()).json()
        self.assertTrue(first['is_mock'])
        self.assertEqual(first['interval_minutes'], 60)
        self.assertEqual(first['unit'], 'kWh')
        self.assertEqual(first['metric'], 'average_energy_per_customer')
        self.assertEqual(first['scenario'], self.scenario())
        self.assertEqual(first['predictions'], second['predictions'])
        self.assertEqual({p['fsa'] for p in first['predictions']}, set(metadata['supported_fsas']))

    def test_input_bounds_and_midnight(self):
        for t in (-40, 35):
            response = self.client.post('/api/v1/predictions', json=self.scenario(temperature_c=t, hour=23))
            self.assertEqual(response.status_code, 200)
        for bad in ({'temperature_c': -41}, {'temperature_c': 36}, {'temperature_c': 1.5}, {'hour': 24}, {'hour': True}, {'day_type': 'monday'}, {'extra': 1}):
            self.assertEqual(self.client.post('/api/v1/predictions', json=self.scenario(**bad)).status_code, 422)

    def test_missing_predictions_are_explicit(self):
        provider = self.client.app.state.predictor
        original = provider.predict_batch
        provider.predict_batch = lambda s, fsas: [Prediction(fsa=fsas[0], value=1.25)]
        try:
            response = self.client.post('/api/v1/predictions', json=self.scenario())
            self.assertEqual(response.status_code, 200)
            rows = response.json()['predictions']
            self.assertEqual(rows[0]['value'], 1.25)
            self.assertTrue(all(p['status'] == 'unsupported' and p['value'] is None for p in rows[1:]))
        finally:
            provider.predict_batch = original

    def test_invalid_provider_output_is_rejected(self):
        provider = self.client.app.state.predictor
        original = provider.predict_batch
        for output in ([{'fsa': 'M5V', 'value': float('nan')}], [{'fsa': 'M5V', 'value': 1}, {'fsa': 'M5V', 'value': 2}], [{'fsa': 'M5V', 'value': None, 'status': 'ok'}]):
            provider.predict_batch = lambda s, fsas, output=output: output
            with self.assertLogs(level='ERROR'):
                self.assertEqual(self.client.post('/api/v1/predictions', json=self.scenario()).status_code, 503)
        provider.predict_batch = original


if __name__ == '__main__':
    unittest.main()
