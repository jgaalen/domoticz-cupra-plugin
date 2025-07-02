# Cupra Domoticz Plugin v2.0.0 - Upgrade Notes

## Overview
This major update addresses critical stability and rate limiting issues that were causing the plugin to fail with "thread seems to have ended unexpectedly" errors and HTTP 429 rate limiting responses.

## Key Issues Fixed

### 1. Thread Stability Issues
**Problem**: The plugin would randomly stop working with "thread seems to have ended unexpectedly" errors.

**Solution**: 
- Implemented a robust worker thread architecture
- Added thread health monitoring in the heartbeat function
- Automatic thread restart when failures are detected
- Proper thread cleanup on plugin stop

### 2. Rate Limiting (HTTP 429 Errors)
**Problem**: Frequent API calls were triggering rate limiting, potentially leading to account blocking.

**Solution**:
- Added configurable rate limiting with minimum delays between requests
- Implemented exponential backoff retry logic for rate limit responses
- Increased default update interval from 60 to 300 seconds (5 minutes)
- Smart detection of HTTP 429 responses with appropriate handling

### 3. Connection Stability
**Problem**: API connection failures would cause the plugin to stop working permanently.

**Solution**:
- Automatic connection retry with exponential backoff
- Connection health monitoring
- Graceful handling of temporary API outages
- Configurable maximum retry attempts

## New Features

### Enhanced Configuration Options
- **Update Interval**: Now defaults to 5 minutes (was 1 minute) to prevent rate limiting
- **Max Retries**: Configurable number of retry attempts (default: 3)
- **Rate Limit Delay**: Minimum time between API requests (default: 2 seconds)
- **Debug Level**: Three levels - Normal, Verbose, Debug for better troubleshooting

### Improved Error Handling
- Comprehensive exception handling for all API operations
- Safe data extraction with fallback values
- Detailed error logging with context
- Graceful degradation when specific data points are unavailable

### Better Logging and Debugging
- Configurable debug levels
- Structured error messages
- Connection status monitoring
- Performance metrics and timing information

## Migration Guide

### Automatic Migration
The plugin will automatically work with existing installations. No manual configuration changes are required.

### Recommended Configuration Changes
After upgrading, consider adjusting these settings in the Domoticz hardware configuration:

1. **Update Interval**: Set to 300+ seconds (5+ minutes) for stable operation
2. **Rate Limit Delay**: Keep at 2+ seconds (increase if you still see rate limiting)
3. **Debug Level**: Use "Normal" for production, "Debug" only for troubleshooting

### What to Expect After Upgrade
- More stable operation with fewer connection drops
- Longer intervals between updates (but more reliable)
- Better recovery from temporary API issues
- Detailed logs for troubleshooting when needed

## Technical Improvements

### Architecture Changes
- **Worker Thread Pattern**: API operations now run in a separate thread
- **Command Queue**: Vehicle commands are queued and executed safely
- **Rate Limiter Class**: Centralized rate limiting with thread safety
- **Retry Handler Class**: Reusable retry logic with exponential backoff

### Error Recovery
- **Connection Monitoring**: Tracks consecutive failures and resets connections
- **Thread Health Checks**: Monitors worker thread status and restarts if needed
- **Graceful Degradation**: Continues operating even if some data points fail

### Performance Optimizations
- **Reduced API Calls**: Longer default intervals reduce server load
- **Smart Updates**: Only updates devices when values actually change
- **Efficient Threading**: Separates blocking operations from Domoticz main thread

## Troubleshooting

### If You Still Experience Issues

1. **Check Update Interval**: Ensure it's set to at least 300 seconds
2. **Monitor Logs**: Look for rate limiting or connection error patterns
3. **Adjust Rate Limiting**: Increase the rate limit delay if needed
4. **Enable Debug Logging**: Temporarily set debug level to "Verbose" or "Debug"

### Common Log Messages

- `"Worker thread restarted successfully"`: Normal recovery from thread failure
- `"Rate limited (HTTP 429), retrying in X seconds"`: Rate limiting detected, automatic retry
- `"Too many consecutive failures, restarting connection"`: Connection reset due to persistent issues
- `"Connection restart initiated"`: Automatic connection recovery

### When to Contact Support

Contact support if you see:
- Continuous thread restarts every few minutes
- Persistent rate limiting despite 5+ minute intervals
- Connection failures that don't recover automatically
- Missing vehicle data after successful connection

## Benefits of v2.0.0

1. **Reliability**: Dramatically reduced plugin crashes and connection drops
2. **Account Safety**: Protection against rate limiting and potential account blocking
3. **Maintainability**: Better error messages and debugging capabilities
4. **Future-Proof**: Robust architecture that can handle API changes better
5. **User Experience**: More predictable operation with better error recovery

## Dependencies

The plugin now includes a `requirements.txt` file with pinned dependency versions:
- weconnect-cupra-daern>=0.6.0
- requests>=2.25.0
- urllib3>=1.26.0

Install with: `pip install -r requirements.txt`

## Backward Compatibility

This update is fully backward compatible with existing installations. All existing device configurations and settings will continue to work without modification.