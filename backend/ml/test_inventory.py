import json
import ai_ml

# Test with different stock levels
test_cases = [
    {
        'name': 'Bandages',
        'quantity': 50,
        'minThreshold': 100,
        'category': 'Consumables'
    },
    {
        'name': 'Ventilators',
        'quantity': 2000,
        'minThreshold': 100,
        'category': 'Equipment'
    },
    {
        'name': 'IV Kits',
        'quantity': 10,
        'minThreshold': 50,
        'category': 'Consumables'
    },
    {
        'name': 'Masks',
        'quantity': 500,
        'minThreshold': 200,
        'category': 'PPE'
    }
]

print("\n" + "="*80)
print("INVENTORY PREDICTION TEST RESULTS")
print("="*80 + "\n")

for i, test in enumerate(test_cases, 1):
    result = ai_ml.predict_inventory(test)
    print(f"Test {i}: {test['name'].upper()}")
    print(f"  Current Stock: {result['current_quantity']} units")
    print(f"  Status: {result['status']}")
    print(f"  Days Left: {result['days_left']} days")
    print(f"  Usage Rate: {result['usage_rate_per_day']} units/day")
    print(f"  Recommendation: {result['recommendation'][:100]}...")
    print()
