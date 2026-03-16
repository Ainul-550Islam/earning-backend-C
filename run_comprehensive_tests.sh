#!/bin/bash
# run_comprehensive_tests.sh

echo "Running Comprehensive API Tests..."
echo "=================================="

echo "\n1. Testing AdNetwork API (with reverse URLs)..."
python manage.py test api.ad_networks.tests_views.AdNetworkAPITests -v 2

echo "\n2. Testing Offer API (with data validation)..."
python manage.py test api.ad_networks.tests_views.OfferAPITests -v 2

echo "\n3. Testing Authenticated CRUD Operations..."
python manage.py test api.ad_networks.tests_views.AuthenticatedCRUDTests -v 2

echo "\n4. Testing Unauthenticated Access..."
python manage.py test api.ad_networks.tests_views.UnauthenticatedAccessTests -v 2

echo "\n5. Running Coverage Report..."
coverage run --source='api/ad_networks' manage.py test api.ad_networks.tests_views
coverage report -m --skip-covered

echo "\n✅ All tests completed!"