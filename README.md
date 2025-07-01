# domoticz-cupra-plugin
Domoticz plugin for Cupra cars (Version 2.0.0)

This plugin fetches the charging and climatisation values and is able to send different commands to the car.

## Version 2.0.0 Updates

### Major Improvements
- **Fixed thread stability issues** - Resolved "thread seems to have ended unexpectedly" errors
- **Added comprehensive rate limiting** - Prevents HTTP 429 errors and account blocking
- **Implemented exponential backoff retry logic** - Handles temporary API failures gracefully  
- **Enhanced error handling** - Better resilience against API connectivity issues
- **Improved logging and debugging** - Configurable debug levels for troubleshooting
- **Worker thread architecture** - Separates API calls from Domoticz main thread
- **Connection monitoring** - Automatic restart of failed connections

### New Configuration Options
- **Update Interval**: Configurable update frequency (default: 5 minutes, recommended for rate limiting)
- **Max Retries**: Number of retry attempts for failed API calls (default: 3)
- **Rate Limit Delay**: Minimum delay between API requests (default: 2 seconds)
- **Debug Level**: Choose between Normal, Verbose, or Debug logging

### Rate Limiting Protection
- Automatic detection of HTTP 429 (Too Many Requests) responses
- Exponential backoff retry strategy
- Configurable minimum delay between API requests
- Connection failure monitoring and automatic recovery

## Installation
From your domoticz home directory:
```bash
cd plugins
git clone https://github.com/jgaalen/domoticz-cupra-plugin.git
pip install -r domoticz-cupra-plugin/requirements.txt
systemctl restart domoticz
```

## Configuration
1. **Update Interval**: Set to at least 300 seconds (5 minutes) to avoid rate limiting
2. **Rate Limit Delay**: Keep at 2+ seconds to prevent overwhelming the API
3. **Max Retries**: 3 retries should be sufficient for most temporary failures
4. **Debug Level**: Use "Debug" only for troubleshooting, "Normal" for production

## Tested on
- Cupra Born

## Troubleshooting

### Thread Ended Unexpectedly
- This issue has been resolved in v2.0.0 with the new worker thread architecture
- The plugin now automatically restarts failed threads
- Monitor the logs for "Worker thread restarted successfully" messages

### Rate Limiting (HTTP 429)
- Increase the "Update Interval" to reduce API call frequency
- Increase the "Rate Limit Delay" to add more time between requests
- The plugin automatically handles rate limiting with exponential backoff

### Connection Issues
- The plugin now automatically retries failed connections
- Check your internet connection and WeConnect credentials
- Monitor consecutive failure counts in the logs

### Debug Information
- Set Debug Level to "Verbose" or "Debug" for detailed logging
- Check Domoticz logs for specific error messages
- Use "Normal" debug level in production to reduce log volume

## Thanks to

This plugin is based on code of: https://pypi.org/project/weconnect-cupra-daern/

## Changelog

### v2.0.0
- Complete rewrite with thread stability improvements
- Added comprehensive rate limiting and retry logic
- Enhanced error handling and connection monitoring
- Configurable update intervals and debug levels
- Fixed thread ending unexpectedly issues
- Protection against account blocking due to rate limits

### v1.0.0
- Initial release




