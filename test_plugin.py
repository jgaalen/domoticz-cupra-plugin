#!/usr/bin/env python3
"""
Test script for Cupra plugin parameter parsing
Run this to test the parameter parsing logic before installing in Domoticz
"""

class MockDomoticz:
    @staticmethod
    def Log(message):
        print(f"LOG: {message}")
    
    @staticmethod
    def Error(message):
        print(f"ERROR: {message}")

# Test cases for parameter parsing
test_cases = [
    # Normal case
    {"Mode2": "300", "Mode3": "3", "Mode4": "2", "Mode5": "Normal"},
    # Empty strings case (the problematic one)
    {"Mode2": "", "Mode3": "", "Mode4": "", "Mode5": ""},
    # Missing parameters case
    {},
    # Invalid values case
    {"Mode2": "abc", "Mode3": "xyz", "Mode4": "invalid", "Mode5": ""},
]

def test_parameter_parsing(Parameters):
    """Test the parameter parsing logic"""
    print(f"\nTesting with Parameters: {Parameters}")
    
    # Simulate the plugin's parameter parsing logic
    try:
        # Check if Parameters exists (safety check)
        if not Parameters:
            print("Parameters object not available, using all defaults")
            update_interval = 300
            max_retries = 3
            rate_limit_delay = 2.0
            debug_level = "Normal"
        else:
            # Parse update interval
            try:
                update_interval_str = Parameters.get("Mode2", "300")
                if not update_interval_str or update_interval_str.strip() == "":
                    update_interval_str = "300"
                update_interval = int(update_interval_str)
                print(f"Update interval set to: {update_interval} seconds")
            except (ValueError, TypeError) as e:
                update_interval = 300
                print(f"Failed to parse update interval, using default 300 seconds. Error: {e}")
                
            # Parse max retries
            try:
                max_retries_str = Parameters.get("Mode3", "3")
                if not max_retries_str or max_retries_str.strip() == "":
                    max_retries_str = "3"
                max_retries = int(max_retries_str)
                print(f"Max retries set to: {max_retries}")
            except (ValueError, TypeError) as e:
                max_retries = 3
                print(f"Failed to parse max retries, using default 3. Error: {e}")
                
            # Parse rate limit delay
            try:
                rate_limit_delay_str = Parameters.get("Mode4", "2")
                if not rate_limit_delay_str or rate_limit_delay_str.strip() == "":
                    rate_limit_delay_str = "2"
                rate_limit_delay = float(rate_limit_delay_str)
                print(f"Rate limit delay set to: {rate_limit_delay} seconds")
            except (ValueError, TypeError) as e:
                rate_limit_delay = 2.0
                print(f"Failed to parse rate limit delay, using default 2.0 seconds. Error: {e}")
                
            # Parse debug level
            debug_level = Parameters.get("Mode5", "Normal") or "Normal"
            if not debug_level or debug_level.strip() == "":
                debug_level = "Normal"
            print(f"Debug level set to: {debug_level}")
            
    except Exception as e:
        print(f"Error parsing parameters: {e}")
        # Use all defaults
        update_interval = 300
        max_retries = 3
        rate_limit_delay = 2.0
        debug_level = "Normal"
        print("Using all default parameter values due to parsing error")
    
    print(f"Final values: interval={update_interval}, retries={max_retries}, delay={rate_limit_delay}, debug={debug_level}")
    return update_interval, max_retries, rate_limit_delay, debug_level

if __name__ == "__main__":
    print("Testing Cupra plugin parameter parsing...")
    
    for i, test_case in enumerate(test_cases):
        print(f"\n{'='*50}")
        print(f"Test Case {i+1}:")
        test_parameter_parsing(test_case)
    
    print(f"\n{'='*50}")
    print("All tests completed!")
    print("\nIf you see this message, the parameter parsing logic should work correctly in Domoticz.")