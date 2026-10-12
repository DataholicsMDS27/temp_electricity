"""Run after npm run build to verify the deployed entrypoint."""

import re
import unittest

from fastapi.testclient import TestClient

from .production import app


class ProductionTests(unittest.TestCase):
    def test_frontend_assets_and_api_share_one_origin(self):
        with TestClient(app) as client:
            page = client.get("/")
            self.assertEqual(page.status_code, 200)
            self.assertIn("text/html", page.headers["content-type"])
            assets = re.findall(r'(?:src|href)="(/assets/[^\"]+)"', page.text)
            self.assertTrue(assets)
            for asset in assets:
                self.assertEqual(client.get(asset).status_code, 200)
            self.assertEqual(client.get("/api/health").json()["status"], "ok")
            metadata = client.get("/api/v1/metadata").json()
            response = client.post("/api/v1/predictions", json={
                "temperature_c": -40, "day_type": "weekend", "hour": 23,
            })
            self.assertEqual(response.status_code, 200)
            self.assertEqual({row["fsa"] for row in response.json()["predictions"]}, set(metadata["supported_fsas"]))
            boundary = client.get("/data/ontario-fsas.geojson", headers={"Accept-Encoding": "gzip"})
            self.assertEqual(boundary.headers["content-encoding"], "gzip")
            self.assertEqual(len(boundary.json()["features"]), len(metadata["supported_fsas"]))
            for path in ("/api/nonexistent", "/.env", "/backend/main.py"):
                self.assertEqual(client.get(path).status_code, 404)


if __name__ == "__main__":
    unittest.main()
