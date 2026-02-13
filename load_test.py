import requests
import time
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


class LoadTester:
    """Generate high volume of predictions to test system"""

    def __init__(self, base_url=None):
        port = os.getenv("PORT", "8000")
        self.base_url = base_url or f"http://localhost:{port}"

        # All leagues
        self.leagues = ["EPL", "LaLiga", "SerieA", "Bundesliga", "Ligue1"]

        # Sample teams per league for testing
        self.teams = {
            "EPL": [
                "Arsenal",
                "Manchester City",
                "Liverpool",
                "Chelsea",
                "Tottenham",
                "Manchester United",
                "Newcastle",
                "Aston Villa",
                "Brighton",
                "West Ham",
                "Crystal Palace",
                "Brentford",
                "Fulham",
                "Wolves",
                "Everton",
                "Nottingham Forest",
                "Bournemouth",
                "Luton Town",
                "Burnley",
                "Sheffield United",
            ],
            "LaLiga": [
                "Real Madrid",
                "Barcelona",
                "Atletico Madrid",
                "Athletic Bilbao",
                "Real Sociedad",
                "Real Betis",
                "Villarreal",
                "Valencia",
                "Sevilla",
                "Girona",
                "Osasuna",
                "Las Palmas",
                "Rayo Vallecano",
                "Getafe",
                "Alaves",
                "Mallorca",
                "Celta Vigo",
                "Cadiz",
                "Granada",
                "Almeria",
            ],
            "SerieA": [
                "Inter Milan",
                "AC Milan",
                "Juventus",
                "Napoli",
                "Roma",
                "Lazio",
                "Atalanta",
                "Fiorentina",
                "Bologna",
                "Torino",
                "Monza",
                "Genoa",
                "Lecce",
                "Udinese",
                "Frosinone",
                "Hellas Verona",
                "Empoli",
                "Cagliari",
                "Sassuolo",
                "Salernitana",
            ],
            "Bundesliga": [
                "Bayern Munich",
                "Borussia Dortmund",
                "RB Leipzig",
                "Union Berlin",
                "Bayer Leverkusen",
                "Eintracht Frankfurt",
                "Freiburg",
                "Wolfsburg",
                "Stuttgart",
                "Hoffenheim",
                "Borussia Monchengladbach",
                "Werder Bremen",
                "Augsburg",
                "Mainz",
                "Heidenheim",
                "Bochum",
                "Koln",
                "Darmstadt",
            ],
            "Ligue1": [
                "PSG",
                "Marseille",
                "Monaco",
                "Lyon",
                "Lille",
                "Nice",
                "Lens",
                "Rennes",
                "Toulouse",
                "Reims",
                "Montpellier",
                "Nantes",
                "Strasbourg",
                "Brest",
                "Le Havre",
                "Lorient",
                "Metz",
                "Clermont",
            ],
        }

        self.predictions_created = []
        self.errors = []

    def create_prediction(self, home_team: str, away_team: str, league: str) -> bool:
        """Create a single prediction"""
        try:
            response = requests.post(
                f"{self.base_url}/api/predict",
                json={"homeTeam": home_team, "awayTeam": away_team, "league": league},
                timeout=5,
            )

            if response.status_code == 201:
                data = response.json()
                self.predictions_created.append(
                    {
                        "id": data.get("predictionId"),
                        "match": f"{home_team} vs {away_team}",
                        "league": league,
                        "prediction": data.get("prediction"),
                        "confidence": data.get("confidence"),
                    }
                )
                return True
            else:
                self.errors.append(
                    f"Failed {home_team} vs {away_team}: {response.status_code}"
                )
                return False

        except Exception as e:
            self.errors.append(f"Error {home_team} vs {away_team}: {str(e)}")
            return False

    def run_light_load_test(self, predictions_per_league: int = 10):
        """
        Light load test - 10 predictions per league
        Total: ~50 predictions
        """
        print("\n" + "=" * 70)
        print("⚽ LIGHT LOAD TEST - 10 predictions per league")
        print("=" * 70)

        start_time = time.time()

        for league in self.leagues:
            print(f"\n🔍 Testing {league}...")
            teams = self.teams[league]
            used_teams = set()

            for i in range(predictions_per_league):
                # Pick teams that haven't played yet
                available = [t for t in teams if t not in used_teams]
                if len(available) < 2:
                    used_teams.clear()
                    available = teams

                import random

                home = random.choice(available)
                available.remove(home)
                away = random.choice(available)

                used_teams.add(home)
                used_teams.add(away)

                success = self.create_prediction(home, away, league)

                if success:
                    pred = self.predictions_created[-1]
                    print(
                        f"   ✅ {pred['match']}: {pred['prediction']} ({pred['confidence']:.0%})"
                    )
                else:
                    print(f"   ❌ Failed to create prediction")

        duration = time.time() - start_time
        self._print_summary(duration, "Light")

    def run_medium_load_test(self, predictions_per_league: int = 30):
        """
        Medium load test - 30 predictions per league
        Total: ~150 predictions
        """
        print("\n" + "=" * 70)
        print("⚽ MEDIUM LOAD TEST - 30 predictions per league")
        print("=" * 70)

        start_time = time.time()

        for league in self.leagues:
            print(f"\n🔍 Testing {league}...")
            teams = self.teams[league]

            count = 0
            for i in range(predictions_per_league):
                import random

                home = random.choice(teams)
                away = random.choice([t for t in teams if t != home])

                success = self.create_prediction(home, away, league)

                if success:
                    count += 1
                    if count % 5 == 0:  # Print every 5th
                        pred = self.predictions_created[-1]
                        print(
                            f"   ✅ Created {count}/{predictions_per_league}: {pred['match']}"
                        )

        duration = time.time() - start_time
        self._print_summary(duration, "Medium")

    def run_heavy_load_test(self, total_predictions: int = 500):
        """
        Heavy load test - 500+ predictions
        Tests system limits
        """
        print("\n" + "=" * 70)
        print(f"⚽ HEAVY LOAD TEST - {total_predictions} predictions")
        print("=" * 70)

        start_time = time.time()
        predictions_per_league = total_predictions // len(self.leagues)

        for league in self.leagues:
            print(f"\n🔍 Testing {league} ({predictions_per_league} predictions)...")
            teams = self.teams[league]

            count = 0
            for i in range(predictions_per_league):
                import random

                home = random.choice(teams)
                away = random.choice([t for t in teams if t != home])

                success = self.create_prediction(home, away, league)

                if success:
                    count += 1
                    if count % 20 == 0:  # Print every 20th
                        print(f"   ✅ Created {count}/{predictions_per_league}")

        duration = time.time() - start_time
        self._print_summary(duration, "Heavy")

    def _print_summary(self, duration: float, test_type: str):
        """Print test summary"""
        total = len(self.predictions_created)
        failed = len(self.errors)

        print("\n" + "=" * 70)
        print(f"📊 {test_type.upper()} LOAD TEST SUMMARY")
        print("=" * 70)

        print(f"\n✅ Successful: {total}")
        print(f"❌ Failed: {failed}")
        print(f"⏱️  Duration: {duration:.2f} seconds")
        print(f"⚡ Rate: {total/duration:.1f} predictions/second")

        # Success rate
        success_rate = (total / (total + failed) * 100) if (total + failed) > 0 else 0
        print(f"📈 Success Rate: {success_rate:.1f}%")

        # Break down by league
        print("\n📊 Breakdown by League:")
        for league in self.leagues:
            league_preds = [
                p for p in self.predictions_created if p["league"] == league
            ]
            print(f"   {league}: {len(league_preds)} predictions")

        # Show some sample predictions
        print("\n🎯 Sample Predictions:")
        import random

        samples = random.sample(
            self.predictions_created, min(5, len(self.predictions_created))
        )
        for pred in samples:
            print(
                f"   {pred['league']}: {pred['match']} → {pred['prediction']} ({pred['confidence']:.0%})"
            )

        # Errors if any
        if self.errors:
            print(f"\n⚠️  Errors ({len(self.errors)}):")
            for error in self.errors[:5]:  # Show first 5 errors
                print(f"   {error}")
            if len(self.errors) > 5:
                print(f"   ... and {len(self.errors) - 5} more")

        print("\n" + "=" * 70)

    def verify_predictions(self):
        """Verify all created predictions are retrievable"""
        print("\n" + "=" * 70)
        print("🔍 VERIFYING PREDICTIONS")
        print("=" * 70)

        try:
            response = requests.get(f"{self.base_url}/api/predictions", timeout=10)

            if response.status_code == 200:
                data = response.json()
                stored = data.get("count", 0)
                created = len(self.predictions_created)

                print(f"\n✅ Created: {created}")
                print(f"📦 Stored in API: {stored}")

                if stored == created:
                    print(f"✅ All predictions successfully stored!")
                else:
                    print(f"⚠️  Mismatch: {created - stored} predictions missing")

                return stored == created
            else:
                print(f"❌ Failed to retrieve predictions: {response.status_code}")
                return False

        except Exception as e:
            print(f"❌ Error verifying: {e}")
            return False

    def get_statistics(self):
        """Get API statistics"""
        try:
            response = requests.get(f"{self.base_url}/api/stats", timeout=5)

            if response.status_code == 200:
                data = response.json()
                stats = data.get("stats", {})

                print("\n" + "=" * 70)
                print("📊 CURRENT API STATISTICS")
                print("=" * 70)
                print(f"\nTotal Predictions: {stats.get('totalPredictions', 0)}")
                print(f"Resolved: {stats.get('resolved', 0)}")
                print(f"Pending: {stats.get('pending', 0)}")
                print(f"Correct: {stats.get('correct', 0)}")
                print(f"Incorrect: {stats.get('incorrect', 0)}")
                print(f"Accuracy: {stats.get('accuracy', 0):.1f}%")
                print("=" * 70)

        except Exception as e:
            print(f"Failed to get stats: {e}")


def main():
    """Run load tests"""
    print("\n" + "=" * 70)
    print("⚽ FOOTYORACLE LOAD TESTING SUITE")
    print("=" * 70)

    # Check if server is running
    tester = LoadTester()

    try:
        response = requests.get(f"{tester.base_url}/health", timeout=2)
        if response.status_code != 200:
            print(f"\n❌ API server not responding correctly")
            print(f"   Make sure server is running: python app.py")
            return
    except:
        print(f"\n❌ Cannot connect to {tester.base_url}")
        print(f"   Make sure server is running: python app.py")
        return

    print(f"\n✅ Connected to API at {tester.base_url}")

    # Get current stats before testing
    tester.get_statistics()

    # Menu
    print("\n" + "=" * 70)
    print("SELECT LOAD TEST TYPE:")
    print("=" * 70)
    print("1. Light Load Test    (~50 predictions,   quick)")
    print("2. Medium Load Test   (~150 predictions,  moderate)")
    print("3. Heavy Load Test    (~500 predictions,  intensive)")
    print("4. Custom Test        (specify amount)")
    print("5. Run All Tests      (sequentially)")
    print("=" * 70)

    choice = input("\nEnter choice (1-5): ").strip()

    if choice == "1":
        tester.run_light_load_test()
        tester.verify_predictions()
        tester.get_statistics()

    elif choice == "2":
        tester.run_medium_load_test()
        tester.verify_predictions()
        tester.get_statistics()

    elif choice == "3":
        tester.run_heavy_load_test()
        tester.verify_predictions()
        tester.get_statistics()

    elif choice == "4":
        try:
            amount = int(input("How many predictions? "))
            if amount > 0:
                tester.run_heavy_load_test(total_predictions=amount)
                tester.verify_predictions()
                tester.get_statistics()
            else:
                print("Invalid amount")
        except ValueError:
            print("Invalid input")

    elif choice == "5":
        print("\n🚀 Running all tests sequentially...\n")

        # Light
        tester.run_light_load_test()

        # Medium
        tester.predictions_created = []
        tester.errors = []
        tester.run_medium_load_test()

        # Heavy
        tester.predictions_created = []
        tester.errors = []
        tester.run_heavy_load_test()

        # Final verification
        tester.verify_predictions()
        tester.get_statistics()

    else:
        print("Invalid choice")

    print("\n✅ Load testing complete!\n")


if __name__ == "__main__":
    main()
