#!/usr/bin/env python3
"""Measure performance of the overview endpoint with 1000+ visits.

This script:
1. Authenticates as the test user (test@test.com)
2. Calls the /api/v1/stats/overview endpoint multiple times
3. Measures response times
4. Reports statistics

Usage:
    # First ensure the backend is running:
    cd backend && uvicorn main:app --reload

    # Then in another terminal:
    cd backend
    python scripts/measure_performance.py

Environment Variables:
    API_BASE_URL: Base URL for API (default: http://localhost:8000)
"""

import os
import sys
import time
import statistics
from datetime import datetime

import requests

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
TEST_EMAIL = "test@test.com"
TEST_PASSWORD = "testpass123"  # You may need to update this


def create_test_user_if_needed():
    """Create test user via signup endpoint if it doesn't exist."""
    signup_url = f"{API_BASE_URL}/api/auth/register"

    payload = {
        "username": "test_perf_user",
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
    }

    try:
        response = requests.post(signup_url, json=payload)
        if response.status_code == 200:
            print(f"Created test user: {TEST_EMAIL}")
            return True
        elif response.status_code == 400 and "already exists" in response.text.lower():
            print(f"Test user already exists: {TEST_EMAIL}")
            return True
        else:
            print(f"Warning: Signup returned {response.status_code}: {response.text}")
            return True  # User might exist
    except Exception as e:
        print(f"Warning: Could not create user: {e}")
        return False


def authenticate() -> str:
    """Authenticate and get JWT token.

    Returns:
        JWT access token
    """
    login_url = f"{API_BASE_URL}/api/auth/login"

    payload = {
        "username": TEST_EMAIL,  # OAuth2 form - can be email or username
        "password": TEST_PASSWORD,
    }

    try:
        response = requests.post(login_url, data=payload)  # Form data for OAuth2
        response.raise_for_status()

        data = response.json()
        return data["access_token"]

    except requests.exceptions.RequestException as e:
        print(f"ERROR: Authentication failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        sys.exit(1)


def measure_overview_performance(token: str, num_requests: int = 10) -> dict:
    """Measure performance of overview endpoint.

    Args:
        token: JWT access token
        num_requests: Number of requests to make for averaging

    Returns:
        Dictionary with performance metrics
    """
    overview_url = f"{API_BASE_URL}/api/v1/stats/overview"
    headers = {"Authorization": f"Bearer {token}"}

    response_times = []
    response_data = None

    print(f"\nMeasuring performance over {num_requests} requests...")
    print("-" * 60)

    for i in range(num_requests):
        start_time = time.perf_counter()

        try:
            response = requests.get(overview_url, headers=headers)
            response.raise_for_status()

            end_time = time.perf_counter()
            elapsed_ms = (end_time - start_time) * 1000

            response_times.append(elapsed_ms)

            # Store first successful response for inspection
            if response_data is None:
                response_data = response.json()

            # Print progress
            status = "PASS" if elapsed_ms < 300 else "SLOW"
            print(f"Request {i+1:2d}: {elapsed_ms:7.2f}ms [{status}]")

        except requests.exceptions.RequestException as e:
            print(f"Request {i+1:2d}: FAILED - {e}")
            continue

    if not response_times:
        print("\nERROR: All requests failed")
        sys.exit(1)

    # Calculate statistics
    metrics = {
        "count": len(response_times),
        "mean": statistics.mean(response_times),
        "median": statistics.median(response_times),
        "min": min(response_times),
        "max": max(response_times),
        "stdev": statistics.stdev(response_times) if len(response_times) > 1 else 0,
        "response_data": response_data,
    }

    return metrics


def print_results(metrics: dict):
    """Print performance test results."""
    print("\n" + "=" * 60)
    print("PERFORMANCE TEST RESULTS")
    print("=" * 60)

    print(f"\nResponse Time Statistics ({metrics['count']} requests):")
    print(f"  Mean:     {metrics['mean']:7.2f}ms")
    print(f"  Median:   {metrics['median']:7.2f}ms")
    print(f"  Min:      {metrics['min']:7.2f}ms")
    print(f"  Max:      {metrics['max']:7.2f}ms")
    print(f"  Std Dev:  {metrics['stdev']:7.2f}ms")

    print(f"\nTarget: < 300ms")
    if metrics['mean'] < 300:
        print(f"Status: PASS (mean {metrics['mean']:.2f}ms < 300ms)")
    else:
        print(f"Status: FAIL (mean {metrics['mean']:.2f}ms >= 300ms)")

    # Show sample response
    if metrics.get('response_data'):
        data = metrics['response_data']
        stats = data.get('stats', {})
        print(f"\nSample Response Data:")
        print(f"  Countries Visited:   {stats.get('countries_visited', 0)}")
        print(f"  Regions Visited:     {stats.get('regions_visited', 0)}")
        print(f"  Cells (res6):        {stats.get('cells_visited_res6', 0)}")
        print(f"  Cells (res8):        {stats.get('cells_visited_res8', 0)}")
        print(f"  Total Visit Count:   {stats.get('total_visit_count', 0)}")
        print(f"  Recent Countries:    {len(data.get('recent_countries', []))}")
        print(f"  Recent Regions:      {len(data.get('recent_regions', []))}")

    print("\n" + "=" * 60)


def save_results_to_file(metrics: dict, filepath: str = "performance_results.txt"):
    """Save performance results to a file."""
    with open(filepath, 'w') as f:
        f.write("Performance Test Results\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Test Date: {datetime.now().isoformat()}\n")
        f.write(f"API URL: {API_BASE_URL}\n")
        f.write(f"Test User: {TEST_EMAIL}\n\n")

        f.write(f"Response Time Statistics ({metrics['count']} requests):\n")
        f.write(f"  Mean:     {metrics['mean']:.2f}ms\n")
        f.write(f"  Median:   {metrics['median']:.2f}ms\n")
        f.write(f"  Min:      {metrics['min']:.2f}ms\n")
        f.write(f"  Max:      {metrics['max']:.2f}ms\n")
        f.write(f"  Std Dev:  {metrics['stdev']:.2f}ms\n\n")

        f.write(f"Target: < 300ms\n")
        if metrics['mean'] < 300:
            f.write(f"Status: PASS (mean {metrics['mean']:.2f}ms < 300ms)\n")
        else:
            f.write(f"Status: FAIL (mean {metrics['mean']:.2f}ms >= 300ms)\n")

        # Add sample data
        if metrics.get('response_data'):
            data = metrics['response_data']
            stats = data.get('stats', {})
            f.write(f"\nSample Response Data:\n")
            f.write(f"  Countries Visited:   {stats.get('countries_visited', 0)}\n")
            f.write(f"  Regions Visited:     {stats.get('regions_visited', 0)}\n")
            f.write(f"  Cells (res6):        {stats.get('cells_visited_res6', 0)}\n")
            f.write(f"  Cells (res8):        {stats.get('cells_visited_res8', 0)}\n")
            f.write(f"  Total Visit Count:   {stats.get('total_visit_count', 0)}\n")
            f.write(f"  Recent Countries:    {len(data.get('recent_countries', []))}\n")
            f.write(f"  Recent Regions:      {len(data.get('recent_regions', []))}\n")

    print(f"\nResults saved to: {filepath}")


def main():
    """Main entry point."""
    print("=" * 60)
    print("Overview Endpoint Performance Test")
    print("=" * 60)
    print(f"API: {API_BASE_URL}")
    print(f"User: {TEST_EMAIL}")
    print()

    # Ensure test user exists
    create_test_user_if_needed()

    # Authenticate
    print("Authenticating...")
    token = authenticate()
    print("Authentication successful!")

    # Measure performance
    metrics = measure_overview_performance(token, num_requests=10)

    # Print results
    print_results(metrics)

    # Save results
    results_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "performance_results.txt"
    )
    save_results_to_file(metrics, results_path)

    # Exit with appropriate code
    if metrics['mean'] < 300:
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
