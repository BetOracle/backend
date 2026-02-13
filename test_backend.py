import requests
import json
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


class BackendTester:
    """Test all backend endpoints"""

    def __init__(self, base_url=None):
        # Get port from environment or use 8000 as default
        port = os.getenv("PORT", "8000")
        self.base_url = base_url or f"http://localhost:{port}"
        self.prediction_id = None

        print(f"Testing API at: {self.base_url}")

    def test_health_check(self):
        """Test health endpoint"""
        print("\n1️⃣  Testing Health Check...")

        response = requests.get(f"{self.base_url}/health")

        if response.status_code == 200:
            print("   ✅ Health check passed")
            print(f"   Response: {response.json()}")
            return True
        else:
            print(f"   ❌ Health check failed: {response.status_code}")
            return False

    def test_create_prediction(self):
        """Test creating a prediction"""
        print("\n2️⃣  Testing Create Prediction...")

        payload = {"homeTeam": "Arsenal", "awayTeam": "Chelsea", "league": "EPL"}

        response = requests.post(f"{self.base_url}/api/predict", json=payload)

        if response.status_code == 201:
            data = response.json()
            self.prediction_id = data.get("predictionId")

            print("   ✅ Prediction created successfully")
            print(f"   Prediction ID: {self.prediction_id}")
            print(f"   Match ID: {data.get('matchId')}")
            print(f"   Prediction: {data.get('prediction')}")
            print(f"   Confidence: {data.get('confidence'):.1%}")
            print(f"   Factors: {data.get('factors')}")
            return True
        else:
            print(f"   ❌ Failed to create prediction: {response.status_code}")
            print(f"   Error: {response.text}")
            return False

    def test_get_all_predictions(self):
        """Test getting all predictions"""
        print("\n3️⃣  Testing Get All Predictions...")

        response = requests.get(f"{self.base_url}/api/predictions")

        if response.status_code == 200:
            data = response.json()
            count = data.get("count", 0)

            print(f"   ✅ Retrieved {count} predictions")

            if count > 0:
                first = data["predictions"][0]
                print(f"   Sample: {first.get('matchId')} - {first.get('prediction')}")

            return True
        else:
            print(f"   ❌ Failed to get predictions: {response.status_code}")
            return False

    def test_get_single_prediction(self):
        """Test getting a specific prediction"""
        print("\n4️⃣  Testing Get Single Prediction...")

        if not self.prediction_id:
            print("   ⚠️  No prediction ID available, skipping...")
            return False

        response = requests.get(f"{self.base_url}/api/predictions/{self.prediction_id}")

        if response.status_code == 200:
            data = response.json()
            pred = data.get("prediction")

            print("   ✅ Retrieved prediction successfully")
            print(f"   Match: {pred.get('matchId')}")
            print(f"   Resolved: {pred.get('resolved')}")
            return True
        else:
            print(f"   ❌ Failed to get prediction: {response.status_code}")
            return False

    def test_get_statistics(self):
        """Test getting statistics"""
        print("\n5️⃣  Testing Get Statistics...")

        response = requests.get(f"{self.base_url}/api/stats")

        if response.status_code == 200:
            data = response.json()
            stats = data.get("stats", {})

            print("   ✅ Retrieved statistics successfully")
            print(f"   Total Predictions: {stats.get('totalPredictions')}")
            print(f"   Resolved: {stats.get('resolved')}")
            print(f"   Pending: {stats.get('pending')}")
            print(f"   Accuracy: {stats.get('accuracy')}%")
            return True
        else:
            print(f"   ❌ Failed to get statistics: {response.status_code}")
            return False

    def test_resolve_prediction(self):
        """Test resolving a prediction"""
        print("\n6️⃣  Testing Resolve Prediction...")

        # First, create a prediction to resolve
        payload = {
            "homeTeam": "Liverpool",
            "awayTeam": "Manchester City",
            "league": "EPL",
        }

        create_response = requests.post(f"{self.base_url}/api/predict", json=payload)

        if create_response.status_code != 201:
            print("   ❌ Failed to create prediction for resolution test")
            return False

        match_id = create_response.json().get("matchId")
        predicted_outcome = create_response.json().get("prediction")

        # Now resolve it
        resolve_payload = {
            "matchId": match_id,
            "actualOutcome": predicted_outcome,  # Mark as correct
        }

        resolve_response = requests.post(
            f"{self.base_url}/api/resolve", json=resolve_payload
        )

        if resolve_response.status_code == 200:
            data = resolve_response.json()

            print("   ✅ Prediction resolved successfully")
            print(f"   Match: {data.get('matchId')}")
            print(f"   Predicted: {data.get('predictedOutcome')}")
            print(f"   Actual: {data.get('actualOutcome')}")
            print(f"   Correct: {data.get('correct')}")
            return True
        else:
            print(f"   ❌ Failed to resolve prediction: {resolve_response.status_code}")
            print(f"   Error: {resolve_response.text}")
            return False

    def run_all_tests(self):
        """Run all tests"""
        print("\n" + "=" * 60)
        print("⚽ FOOTYORACLE BACKEND TEST SUITE")
        print("=" * 60)

        results = []

        # Run tests
        results.append(("Health Check", self.test_health_check()))
        results.append(("Create Prediction", self.test_create_prediction()))
        results.append(("Get All Predictions", self.test_get_all_predictions()))
        results.append(("Get Single Prediction", self.test_get_single_prediction()))
        results.append(("Get Statistics", self.test_get_statistics()))
        results.append(("Resolve Prediction", self.test_resolve_prediction()))

        # Summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)

        passed = sum(1 for _, result in results if result)
        total = len(results)

        for test_name, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status} - {test_name}")

        print("\n" + "=" * 60)
        print(f"Results: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
        print("=" * 60 + "\n")

        return passed == total


if __name__ == "__main__":
    # Test against local server (reads PORT from .env or defaults to 8000)
    tester = BackendTester()

    try:
        success = tester.run_all_tests()

        if success:
            print("🎉 All tests passed! Backend is working correctly.")
            exit(0)
        else:
            print("⚠️  Some tests failed. Check the output above.")
            exit(1)

    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Could not connect to backend server")
        print(f"   Make sure the server is running on {tester.base_url}")
        print("   python app.py")
        exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        exit(1)
